"""User and system information tools."""
from __future__ import annotations

import json
from anthropic import beta_tool

_USER_DB = {
    "usr-42": {"user_id": "usr-42", "name": "Alice Rossi", "email": "alice@example.com",
               "department": "Engineering", "is_vip": False, "past_ticket_count": 3},
    "usr-07": {"user_id": "usr-07", "name": "Bob CEO", "email": "bob.ceo@example.com",
               "department": "Executive", "is_vip": True, "past_ticket_count": 1},
    "usr-99": {"user_id": "usr-99", "name": "Charlie Ops", "email": "charlie@example.com",
               "department": "Operations", "is_vip": False, "past_ticket_count": 12},
}


@beta_tool
def get_user_info(user_id: str) -> str:
    """Return profile information for a user, including VIP status and ticket history.

    Args:
        user_id: The user identifier, e.g. 'usr-42'.
    """
    user = _USER_DB.get(user_id)
    if user is None:
        return json.dumps({
            "status": "error",
            "code": "USER_NOT_FOUND",
            "message": f"No user found with id '{user_id}'",
            "retryable": False,
        })
    return json.dumps({"status": "ok", "data": user})
