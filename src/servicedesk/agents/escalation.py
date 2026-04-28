"""Escalation subagent — decides whether and how to escalate based on 3-factor logic."""
from __future__ import annotations

from anthropic import AnthropicBedrock
from servicedesk.config import (
    ESCALATION_MODEL,
    LOW_CONFIDENCE_THRESHOLD,
    AUTO_ROUTE_CONFIDENCE,
    AWS_PROFILE,
)
from servicedesk.models.schemas import (
    IncomingTicket,
    UserInfo,
    TriageResult,
    RoutingResult,
    EscalationResult,
    EscalationTier,
)


_client = AnthropicBedrock(aws_profile=AWS_PROFILE)

_SYSTEM_PROMPT = [
    {
        "type": "text",
        "text": """You are an escalation agent for an IT service desk. You receive a fully triaged
and routed ticket and must decide whether it needs escalation beyond normal handling.

## Escalation tiers
- none: Standard handling; route to assigned team as-is.
- l2: Second-level support; needed for VIP users, medium confidence, or P2 issues.
- l3: Engineering escalation; needed for low confidence on high-impact tickets,
  or complex technical issues beyond L2 scope.
- management: Executive/management notification; needed for outages with critical impact
  or extended duration threats.
- security: Security team escalation; mandatory for security_incident or phishing categories.

## Hard rules (always apply, regardless of other factors)
1. category = security_incident OR security/phishing → tier = security, should_escalate = true.
2. category = outage AND impact = critical → tier = management, should_escalate = true.
3. confidence < 0.40 AND impact in [high, critical] → tier = l3, should_escalate = true.
4. is_vip = true AND priority in [P1, P2] → tier = l2 minimum, should_escalate = true.

## Soft rules (use judgment)
5. confidence >= 0.80 AND impact in [low, medium] → tier = none, should_escalate = false.
6. priority = P1 → at least l2 unless already security or management.

## notify_targets
List user IDs or team IDs that should be notified. For management tier, include 'team-exec'.
For security tier, include 'team-security'. For l3, include the assigned team lead.
For VIP escalations, include the requester's user_id.
""",
        "cache_control": {"type": "ephemeral"},
    }
]


def _fast_path(
    triage: TriageResult, user: UserInfo
) -> EscalationResult | None:
    """Return a result immediately for cases covered by hard rules, skipping the LLM."""
    cat = triage.category
    imp = triage.impact.value
    conf = triage.confidence

    if cat in ("security_incident",):
        return EscalationResult(
            should_escalate=True,
            escalation_tier=EscalationTier.SECURITY,
            reason="Security incident — mandatory security team escalation.",
            notify_targets=["team-security", user.user_id],
        )

    if cat == "outage" and imp == "critical":
        targets = ["team-exec", "team-sre", user.user_id]
        if user.is_vip:
            targets.append(user.user_id)
        return EscalationResult(
            should_escalate=True,
            escalation_tier=EscalationTier.MANAGEMENT,
            reason="Critical outage — management notification required.",
            notify_targets=list(dict.fromkeys(targets)),
        )

    if conf < LOW_CONFIDENCE_THRESHOLD and imp in ("high", "critical"):
        return EscalationResult(
            should_escalate=True,
            escalation_tier=EscalationTier.L3,
            reason=f"Low triage confidence ({conf:.0%}) on high-impact ticket — L3 review needed.",
            notify_targets=["team-l3"],
        )

    if conf >= AUTO_ROUTE_CONFIDENCE and imp in ("low", "medium") and not user.is_vip:
        return EscalationResult(
            should_escalate=False,
            escalation_tier=EscalationTier.NONE,
            reason="High confidence, low-to-medium impact — auto-routed without escalation.",
            notify_targets=[],
        )

    return None


def run_escalation(
    ticket: IncomingTicket,
    user: UserInfo,
    triage: TriageResult,
    routing: RoutingResult,
) -> EscalationResult:
    """Decide escalation tier; uses deterministic fast-path where possible, LLM otherwise."""
    fast = _fast_path(triage, user)
    if fast is not None:
        return fast

    user_message = f"""Ticket: {ticket.ticket_id}
Subject: {ticket.subject}

Requester: {user.name} | VIP: {user.is_vip} | Dept: {user.department}
Category: {triage.category} | Priority: {triage.priority} | Impact: {triage.impact}
Confidence: {triage.confidence:.2f} | Summary: {triage.summary}
Routed to: {routing.team_id} ({routing.queue}) | SLA: {routing.sla_minutes} min

Determine whether this ticket needs escalation, which tier, the reason, and who to notify.
"""

    response = _client.messages.create(
        model=ESCALATION_MODEL,
        max_tokens=512,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        tools=[{
            "name": "result",
            "description": "Return the escalation decision.",
            "input_schema": EscalationResult.model_json_schema(),
        }],
        tool_choice={"type": "tool", "name": "result"},
    )
    for block in response.content:
        if block.type == "tool_use":
            return EscalationResult(**block.input)
    raise ValueError("Escalation subagent returned no tool_use block")
