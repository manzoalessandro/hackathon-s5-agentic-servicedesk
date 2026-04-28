"""Notification and assignment tools — backed by an in-memory mock."""
from __future__ import annotations

import json
from anthropic import beta_tool

_NOTIFICATION_LOG: list[dict] = []
_ASSIGNMENT_LOG: list[dict] = []


@beta_tool
def notify_user(user_id: str, message: str) -> str:
    """Send a notification message to a specific user.

    Args:
        user_id: The user identifier to notify, e.g. 'usr-42'.
        message: The notification message body.
    """
    if not message.strip():
        return json.dumps({
            "status": "error",
            "code": "EMPTY_MESSAGE",
            "message": "Notification message cannot be empty",
            "retryable": False,
        })

    record = {"type": "user", "recipient": user_id, "message": message}
    _NOTIFICATION_LOG.append(record)
    return json.dumps({"status": "ok", "data": {"sent": True, "recipient": user_id}})


@beta_tool
def notify_team(team_id: str, message: str, priority: str = "normal") -> str:
    """Broadcast a notification to all members of a team.

    Args:
        team_id: The team identifier, e.g. 'team-sre'.
        message: The notification message body.
        priority: One of 'low', 'normal', 'high', 'urgent'.
    """
    valid_priorities = {"low", "normal", "high", "urgent"}
    if priority not in valid_priorities:
        return json.dumps({
            "status": "error",
            "code": "INVALID_PRIORITY",
            "message": f"Priority must be one of {sorted(valid_priorities)}, got '{priority}'",
            "retryable": False,
        })

    if not message.strip():
        return json.dumps({
            "status": "error",
            "code": "EMPTY_MESSAGE",
            "message": "Notification message cannot be empty",
            "retryable": False,
        })

    record = {"type": "team", "recipient": team_id, "message": message, "priority": priority}
    _NOTIFICATION_LOG.append(record)
    return json.dumps({"status": "ok", "data": {"sent": True, "recipient": team_id, "priority": priority}})


@beta_tool
def assign_ticket(ticket_id: str, team_id: str, assignee_id: str = "") -> str:
    """Assign a ticket to a team and optionally to a specific agent.

    Args:
        ticket_id: The ticket to assign, e.g. 'TKT-001'.
        team_id: The team taking ownership, e.g. 'team-netops'.
        assignee_id: Optional individual agent user ID within the team.
    """
    from servicedesk.tools.ticket import _TICKET_STORE

    ticket = _TICKET_STORE.get(ticket_id)
    if ticket is None:
        return json.dumps({
            "status": "error",
            "code": "TICKET_NOT_FOUND",
            "message": f"No ticket found with id '{ticket_id}'",
            "retryable": False,
        })

    ticket["team_id"] = team_id
    if assignee_id:
        ticket["assignee_id"] = assignee_id

    record = {"ticket_id": ticket_id, "team_id": team_id, "assignee_id": assignee_id or None}
    _ASSIGNMENT_LOG.append(record)
    return json.dumps({"status": "ok", "data": {"ticket_id": ticket_id, "team_id": team_id, "assignee_id": assignee_id or None}})
