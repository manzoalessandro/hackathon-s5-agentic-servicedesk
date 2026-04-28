"""Unit tests for the routing subagent — verifies fast-path deterministic routing."""
from __future__ import annotations

from servicedesk.models.schemas import TriageResult, Priority, Impact
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

    def fake_parse(**kwargs):
        called.append(True)
        from unittest.mock import MagicMock
        from servicedesk.models.schemas import RoutingResult
        r = MagicMock()
        r.parsed = RoutingResult(
            team_id="team-sre",
            queue="incident-queue",
            sla_minutes=15,
            assignment_note="LLM routed",
        )
        return r

    import servicedesk.agents.routing as routing_mod
    monkeypatch.setattr(routing_mod._client.beta.messages, "parse", fake_parse)

    routing_mod.run_routing(_triage("outage", confidence=0.60))
    assert called, "Expected LLM call for low-confidence routing"
