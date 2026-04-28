"""Unit tests for the triage subagent — mocks the Anthropic client."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from servicedesk.models.schemas import (
    IncomingTicket, UserInfo, TriageResult, Priority, Impact
)


_DUMMY_TICKET = IncomingTicket(
    ticket_id="TKT-TEST",
    subject="VPN not working",
    body="Cannot connect since this morning.",
    requester_id="usr-42",
    created_at="2026-04-28T08:00:00Z",
)

_DUMMY_USER = UserInfo(
    user_id="usr-42",
    name="Alice",
    email="alice@example.com",
    department="Engineering",
    is_vip=False,
)

_EXPECTED_TRIAGE = TriageResult(
    category="network_issue",
    priority=Priority.P3,
    confidence=0.85,
    impact=Impact.LOW,
    summary="User cannot connect to VPN.",
    tags=["vpn"],
)

# Simulate a tool_use block returned by Bedrock
def _mock_tool_use_response(data: dict):
    block = MagicMock()
    block.type = "tool_use"
    block.input = data
    response = MagicMock()
    response.content = [block]
    return response


def test_run_triage_returns_triage_result():
    mock_response = _mock_tool_use_response(_EXPECTED_TRIAGE.model_dump())

    with patch("servicedesk.agents.triage._client") as mock_client:
        mock_client.messages.create.return_value = mock_response
        from servicedesk.agents.triage import run_triage
        result = run_triage(_DUMMY_TICKET, _DUMMY_USER)

    assert result.category == "network_issue"
    assert result.priority == Priority.P3
    assert result.confidence == pytest.approx(0.85)


def test_run_triage_passes_correct_model():
    mock_response = _mock_tool_use_response(_EXPECTED_TRIAGE.model_dump())

    with patch("servicedesk.agents.triage._client") as mock_client:
        mock_client.messages.create.return_value = mock_response
        from servicedesk.agents.triage import run_triage
        run_triage(_DUMMY_TICKET, _DUMMY_USER)

    call_kwargs = mock_client.messages.create.call_args[1]
    assert "haiku" in call_kwargs["model"]
    assert call_kwargs["tool_choice"] == {"type": "tool", "name": "result"}
