"""Ticket CRUD tools — backed by an in-memory mock store."""
from __future__ import annotations

import json
from anthropic import beta_tool

# In-memory store so we can run without a real backend during demos/tests.
_TICKET_STORE: dict[str, dict] = {}


def _seed_demo_tickets() -> None:
    _TICKET_STORE["TKT-001"] = {
        "ticket_id": "TKT-001",
        "subject": "Cannot login to VPN",
        "body": "Since this morning I can't connect to the corporate VPN. Error: 'Authentication failed'.",
        "requester_id": "usr-42",
        "status": "open",
        "priority": None,
        "team_id": None,
        "created_at": "2026-04-28T08:00:00Z",
    }
    _TICKET_STORE["TKT-002"] = {
        "ticket_id": "TKT-002",
        "subject": "URGENT: prod database down",
        "body": "All writes to the production Postgres cluster are failing with 'connection refused'. Revenue impact.",
        "requester_id": "usr-07",
        "status": "open",
        "priority": None,
        "team_id": None,
        "created_at": "2026-04-28T09:15:00Z",
    }


_seed_demo_tickets()


@beta_tool
def lookup_ticket(ticket_id: str) -> str:
    """Return full details for a ticket by its ID.

    Args:
        ticket_id: The ticket identifier, e.g. 'TKT-001'.
    """
    ticket = _TICKET_STORE.get(ticket_id)
    if ticket is None:
        return json.dumps({
            "status": "error",
            "code": "TICKET_NOT_FOUND",
            "message": f"No ticket found with id '{ticket_id}'",
            "retryable": False,
        })
    return json.dumps({"status": "ok", "data": ticket})


@beta_tool
def update_ticket(ticket_id: str, updates: dict) -> str:
    """Patch one or more fields on an existing ticket.

    Args:
        ticket_id: The ticket to update.
        updates: Dict of field names → new values.  Allowed fields: status,
                 priority, team_id, assignee_id, escalation_tier, tags.
    """
    allowed = {"status", "priority", "team_id", "assignee_id", "escalation_tier", "tags"}
    bad = set(updates) - allowed
    if bad:
        return json.dumps({
            "status": "error",
            "code": "INVALID_FIELDS",
            "message": f"Unknown fields: {sorted(bad)}. Allowed: {sorted(allowed)}",
            "retryable": False,
        })

    ticket = _TICKET_STORE.get(ticket_id)
    if ticket is None:
        return json.dumps({
            "status": "error",
            "code": "TICKET_NOT_FOUND",
            "message": f"No ticket found with id '{ticket_id}'",
            "retryable": False,
        })

    ticket.update(updates)
    return json.dumps({"status": "ok", "data": ticket})


@beta_tool
def create_ticket(subject: str, body: str, requester_id: str) -> str:
    """Open a new ticket and return its ID.

    Args:
        subject: Short title (max 120 chars).
        body: Full description of the issue.
        requester_id: ID of the user raising the ticket.
    """
    import uuid
    import datetime as dt

    new_id = f"TKT-{str(uuid.uuid4())[:8].upper()}"
    ticket = {
        "ticket_id": new_id,
        "subject": subject[:120],
        "body": body,
        "requester_id": requester_id,
        "status": "open",
        "priority": None,
        "team_id": None,
        "created_at": dt.datetime.now(dt.UTC).isoformat(),
    }
    _TICKET_STORE[new_id] = ticket
    return json.dumps({"status": "ok", "data": {"ticket_id": new_id}})
