"""Routing subagent — maps a classified ticket to the correct team and queue."""
from __future__ import annotations

import anthropic
from servicedesk.config import ROUTING_MODEL, ROUTING_MATRIX
from servicedesk.models.schemas import TriageResult, RoutingResult


_client = anthropic.Anthropic()

_ROUTING_TABLE_TEXT = "\n".join(
    f"- {cat}: team={team}, queue={queue}, sla={sla}min"
    for cat, (team, queue, sla) in ROUTING_MATRIX.items()
)

_SYSTEM_PROMPT = [
    {
        "type": "text",
        "text": f"""You are a routing agent for an IT service desk. Given a pre-classified ticket,
select the correct team and queue and write a concise assignment note.

## Routing matrix
{_ROUTING_TABLE_TEXT}

## Assignment note
Write one sentence explaining why this ticket goes to this team.
Include SLA context (e.g. "SLA: 120 min").
""",
        "cache_control": {"type": "ephemeral"},
    }
]


def run_routing(triage: TriageResult) -> RoutingResult:
    """Call the routing subagent and return a structured RoutingResult."""
    # Fast path: if category maps directly and confidence is high, derive routing
    # deterministically without an LLM call to save tokens.
    if triage.category in ROUTING_MATRIX and triage.confidence >= 0.80:
        team_id, queue, sla_minutes = ROUTING_MATRIX[triage.category]
        return RoutingResult(
            team_id=team_id,
            queue=queue,
            sla_minutes=sla_minutes,
            assignment_note=(
                f"Auto-routed to {team_id} ({queue}) based on category "
                f"'{triage.category}' with {triage.confidence:.0%} confidence. SLA: {sla_minutes} min."
            ),
        )

    user_message = f"""Category: {triage.category}
Priority: {triage.priority}
Impact: {triage.impact}
Confidence: {triage.confidence:.2f}
Summary: {triage.summary}
Tags: {", ".join(triage.tags) if triage.tags else "none"}

Select the correct team and queue from the routing matrix and write an assignment note.
"""

    response = _client.beta.messages.parse(
        model=ROUTING_MODEL,
        max_tokens=256,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        response_format=RoutingResult,
    )
    return response.parsed
