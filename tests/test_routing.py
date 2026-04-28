"""Unit tests for the routing subagent — verifies fast-path deterministic routing."""
from __future__ import annotations

from unittest.mock import MagicMock
from servicedesk.models.schemas import TriageResult, Priority, Impact, RoutingResult
from servicedesk.agents.routing import run_routing
from servicedesk.config import ROUTING_MATRIX


def _triage(category: str, confidence: float = 0.85) -> TriageResult:
    return TriageResult(
        category=category,
        priority=Priority.P2,
        confidence=confidence,
        impact=Impact.MEDIUM,
        summary="test ticket",
        tags=[],
    )


def _mock_tool_use_response(data: dict):
    block = MagicMock()
    block.type = "tool_use"
    block.input = data
    response = MagicMock()
    response.content = [block]
    return response


def test_high_confidence_uses_fast_path_without_llm():
    # High confidence → deterministic fast-path, no API call
    result = run_routing(_triage("outage", confidence=0.95))
    expected_team, expected_queue, expected_sla = ROUTING_MATRIX["outage"]
    assert result.team_id == expected_team
    assert result.queue == expected_queue
    assert result.sla_minutes == expected_sla


def test_fast_path_all_categories():
    for category in ROUTING_MATRIX:
        result = run_routing(_triage(category, confidence=0.90))
        team, queue, sla = ROUTING_MATRIX[category]
        assert result.team_id == team
        assert result.queue == queue
        assert result.sla_minutes == sla


def test_low_confidence_does_not_use_fast_path(monkeypatch):
    called = []
    expected_result = RoutingResult(
        team_id="team-sre",
        queue="incident-queue",
        sla_minutes=15,
        assignment_note="LLM routed",
    )

    def fake_create(**kwargs):
        called.append(True)
        return _mock_tool_use_response(expected_result.model_dump())

    import servicedesk.agents.routing as routing_mod
    monkeypatch.setattr(routing_mod._client.messages, "create", fake_create)

    routing_mod.run_routing(_triage("outage", confidence=0.60))
    assert called, "Expected LLM call for low-confidence routing"
