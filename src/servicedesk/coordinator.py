"""Coordinator agent — orchestrates triage → routing + escalation → tool execution."""
from __future__ import annotations

import json
import anthropic

from servicedesk.config import COORDINATOR_MODEL
from servicedesk.models.schemas import (
    IncomingTicket,
    UserInfo,
    TicketDecision,
)
from servicedesk.agents.triage import run_triage
from servicedesk.agents.routing import run_routing
from servicedesk.agents.escalation import run_escalation
from servicedesk.tools import (
    lookup_ticket,
    update_ticket,
    get_user_info,
    assign_ticket,
    notify_user,
    notify_team,
    search_knowledge_base,
    get_similar_tickets,
)


_client = anthropic.Anthropic()

_COORDINATOR_TOOLS = [
    lookup_ticket,
    update_ticket,
    get_user_info,
    assign_ticket,
    notify_user,
    notify_team,
    search_knowledge_base,
    get_similar_tickets,
]

_SYSTEM_PROMPT = [
    {
        "type": "text",
        "text": """You are the coordinator for an IT service desk automation pipeline.

Your job is to process a single support ticket through three stages:
1. Enrich context — look up the ticket and requester details using available tools.
2. Validate — confirm the triage/routing/escalation decisions already provided.
3. Execute — update the ticket, assign it, and send notifications as required.

## Tool usage rules
- Always call lookup_ticket first to confirm ticket state.
- Always call get_user_info to confirm requester details before acting.
- Call update_ticket to set status='in_progress', priority, and team_id.
- Call assign_ticket with the routing result's team_id.
- If should_escalate=true, call notify_team for each escalation notify_target.
- If the requester is VIP, call notify_user to acknowledge receipt personally.
- Search knowledge_base or similar_tickets only when confidence < 0.70.
- Never loop more than 8 tool calls for a single ticket.

## Output
After completing tool calls, output a single JSON object matching TicketDecision schema
with coordinator_notes summarising what actions were taken.
""",
        "cache_control": {"type": "ephemeral"},
    }
]


def _run_tool(name: str, tool_input: dict) -> str:
    tool_map = {t.__name__: t for t in _COORDINATOR_TOOLS}
    fn = tool_map.get(name)
    if fn is None:
        return json.dumps({
            "status": "error",
            "code": "UNKNOWN_TOOL",
            "message": f"No tool named '{name}'",
            "retryable": False,
        })
    try:
        return fn(**tool_input)
    except Exception as exc:
        return json.dumps({
            "status": "error",
            "code": "TOOL_EXCEPTION",
            "message": str(exc),
            "retryable": True,
        })


def process_ticket(ticket_id: str) -> TicketDecision:
    """Full pipeline: enrich → triage → route → escalate → execute tools → return decision."""

    # ── Stage 1: Fetch raw ticket ─────────────────────────────────────────────
    raw = json.loads(lookup_ticket(ticket_id))
    if raw["status"] != "ok":
        raise ValueError(f"Cannot fetch ticket {ticket_id}: {raw['message']}")
    t_data = raw["data"]

    ticket = IncomingTicket(
        ticket_id=t_data["ticket_id"],
        subject=t_data["subject"],
        body=t_data["body"],
        requester_id=t_data["requester_id"],
        created_at=t_data["created_at"],
    )

    # ── Stage 2: Fetch user ───────────────────────────────────────────────────
    raw_user = json.loads(get_user_info(ticket.requester_id))
    if raw_user["status"] != "ok":
        # Graceful degradation — create minimal user record
        user = UserInfo(
            user_id=ticket.requester_id,
            name="Unknown",
            email="",
            department="Unknown",
        )
    else:
        user = UserInfo(**raw_user["data"])

    # ── Stage 3: Subagents ────────────────────────────────────────────────────
    triage = run_triage(ticket, user)
    routing = run_routing(triage)
    escalation = run_escalation(ticket, user, triage, routing)

    # ── Stage 4: Coordinator tool-loop ────────────────────────────────────────
    decision_context = f"""Ticket: {ticket.ticket_id}
Subject: {ticket.subject}
Requester: {user.name} (VIP: {user.is_vip})

Triage result:
  category={triage.category}, priority={triage.priority},
  impact={triage.impact}, confidence={triage.confidence:.2f}
  summary="{triage.summary}"

Routing result:
  team={routing.team_id}, queue={routing.queue},
  sla={routing.sla_minutes}min
  note="{routing.assignment_note}"

Escalation result:
  should_escalate={escalation.should_escalate}, tier={escalation.escalation_tier},
  reason="{escalation.reason}"
  notify_targets={escalation.notify_targets}

Execute the required tool calls, then output the final TicketDecision JSON.
"""

    messages: list[dict] = [{"role": "user", "content": decision_context}]
    tool_call_count = 0
    coordinator_notes: list[str] = []

    while tool_call_count < 8:
        response = _client.beta.messages.create(
            model=COORDINATOR_MODEL,
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            tools=_COORDINATOR_TOOLS,
            messages=messages,
            thinking={"type": "adaptive"},
            betas=["interleaved-thinking-2025-05-14"],
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                tool_call_count += 1
                result_str = _run_tool(block.name, block.input)
                coordinator_notes.append(f"{block.name}({json.dumps(block.input)}) → {result_str[:120]}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_str,
                })
            messages.append({"role": "user", "content": tool_results})
        else:
            break

    # ── Stage 5: Build final TicketDecision ───────────────────────────────────
    return TicketDecision(
        ticket_id=ticket.ticket_id,
        triage=triage,
        routing=routing,
        escalation=escalation,
        coordinator_notes="; ".join(coordinator_notes) or "Pipeline completed.",
    )
