"""Unit tests for tool functions — no API calls needed."""
from __future__ import annotations

import json
import pytest
from servicedesk.tools.ticket import lookup_ticket, update_ticket, create_ticket, _TICKET_STORE
from servicedesk.tools.knowledge_base import search_knowledge_base, get_similar_tickets
from servicedesk.tools.system_info import get_user_info
from servicedesk.tools.notification import notify_user, notify_team, assign_ticket


# ── ticket tools ──────────────────────────────────────────────────────────────

def test_lookup_existing_ticket():
    result = json.loads(lookup_ticket("TKT-001"))
    assert result["status"] == "ok"
    assert result["data"]["ticket_id"] == "TKT-001"


def test_lookup_missing_ticket():
    result = json.loads(lookup_ticket("TKT-MISSING"))
    assert result["status"] == "error"
    assert result["code"] == "TICKET_NOT_FOUND"


def test_update_ticket_valid_field():
    result = json.loads(update_ticket("TKT-001", {"priority": "P1"}))
    assert result["status"] == "ok"
    assert result["data"]["priority"] == "P1"


def test_update_ticket_invalid_field():
    result = json.loads(update_ticket("TKT-001", {"subject": "hacked"}))
    assert result["status"] == "error"
    assert result["code"] == "INVALID_FIELDS"


def test_create_ticket_returns_id():
    result = json.loads(create_ticket("Test subject", "Test body", "usr-42"))
    assert result["status"] == "ok"
    assert result["data"]["ticket_id"].startswith("TKT-")


# ── knowledge base ────────────────────────────────────────────────────────────

def test_search_kb_returns_articles():
    result = json.loads(search_knowledge_base("vpn network access"))
    assert result["status"] == "ok"
    assert result["data"]["total"] >= 1
    assert result["data"]["articles"][0]["id"] == "KB-001"


def test_search_kb_no_results():
    result = json.loads(search_knowledge_base("xyzzy frobble"))
    assert result["status"] == "ok"
    assert result["data"]["total"] == 0


def test_similar_tickets_match():
    result = json.loads(get_similar_tickets("VPN authentication failure"))
    assert result["status"] == "ok"
    assert result["data"]["total"] >= 1


# ── user info ─────────────────────────────────────────────────────────────────

def test_get_known_user():
    result = json.loads(get_user_info("usr-07"))
    assert result["status"] == "ok"
    assert result["data"]["is_vip"] is True


def test_get_unknown_user():
    result = json.loads(get_user_info("usr-999"))
    assert result["status"] == "error"
    assert result["code"] == "USER_NOT_FOUND"


# ── notifications ─────────────────────────────────────────────────────────────

def test_notify_user_ok():
    result = json.loads(notify_user("usr-42", "Your ticket was received."))
    assert result["status"] == "ok"


def test_notify_user_empty_message():
    result = json.loads(notify_user("usr-42", "  "))
    assert result["status"] == "error"
    assert result["code"] == "EMPTY_MESSAGE"


def test_notify_team_invalid_priority():
    result = json.loads(notify_team("team-sre", "Alert", priority="mega"))
    assert result["status"] == "error"
    assert result["code"] == "INVALID_PRIORITY"


def test_assign_ticket_ok():
    result = json.loads(assign_ticket("TKT-002", "team-sre"))
    assert result["status"] == "ok"
    assert _TICKET_STORE["TKT-002"]["team_id"] == "team-sre"
