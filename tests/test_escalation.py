"""Unit tests for the escalation subagent — focuses on hard-rule fast-paths."""
from __future__ import annotations

import pytest
from servicedesk.models.schemas import (
    IncomingTicket, UserInfo, TriageResult, RoutingResult,
    Priority, Impact, EscalationTier
)
from servicedesk.agents.escalation import _fast_path


def _ticket():
    return IncomingTicket(
        ticket_id="TKT-X",
        subject="test",
        body="test",
        requester_id="usr-42",
        created_at="2026-04-28T08:00:00Z",
    )

def _user(is_vip=False):
    return UserInfo(
        user_id="usr-42",
        name="Alice",
        email="a@e.com",
        department="Eng",
        is_vip=is_vip,
    )

def _triage(category="network_issue", priority=Priority.P3, impact=Impact.LOW, confidence=0.85):
    return TriageResult(
        category=category,
        priority=priority,
        confidence=confidence,
        impact=impact,
        summary="test",
        tags=[],
    )


def test_security_incident_always_escalates():
    result = _fast_path(_triage(category="security_incident", impact=Impact.HIGH), _user())
    assert result is not None
    assert result.escalation_tier == EscalationTier.SECURITY
    assert result.should_escalate is True


def test_critical_outage_goes_to_management():
    result = _fast_path(_triage(category="outage", impact=Impact.CRITICAL, priority=Priority.P1), _user())
    assert result is not None
    assert result.escalation_tier == EscalationTier.MANAGEMENT
    assert result.should_escalate is True


def test_low_confidence_high_impact_goes_to_l3():
    result = _fast_path(_triage(confidence=0.30, impact=Impact.HIGH), _user())
    assert result is not None
    assert result.escalation_tier == EscalationTier.L3
    assert result.should_escalate is True


def test_high_confidence_low_impact_no_escalation():
    result = _fast_path(_triage(confidence=0.92, impact=Impact.LOW), _user(is_vip=False))
    assert result is not None
    assert result.escalation_tier == EscalationTier.NONE
    assert result.should_escalate is False


def test_high_confidence_low_impact_vip_returns_none_for_llm():
    # VIP + high confidence + low impact → falls through to LLM (returns None from fast_path)
    result = _fast_path(_triage(confidence=0.92, impact=Impact.LOW), _user(is_vip=True))
    assert result is None


def test_ambiguous_case_falls_through_to_llm():
    # Medium confidence, medium impact, non-VIP → no hard rule applies → None
    result = _fast_path(_triage(confidence=0.60, impact=Impact.MEDIUM), _user())
    assert result is None
