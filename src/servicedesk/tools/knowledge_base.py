"""Knowledge base and similar-ticket search tools."""
from __future__ import annotations

import json
from anthropic import beta_tool

_KB_ARTICLES = [
    {"id": "KB-001", "title": "VPN troubleshooting guide", "tags": ["vpn", "network", "access"]},
    {"id": "KB-002", "title": "Password reset procedure", "tags": ["access", "auth"]},
    {"id": "KB-003", "title": "Incident response playbook", "tags": ["incident", "outage", "sre"]},
    {"id": "KB-004", "title": "Database recovery runbook", "tags": ["database", "outage", "data"]},
    {"id": "KB-005", "title": "Phishing response protocol", "tags": ["security", "phishing"]},
]

_PAST_TICKETS = [
    {"ticket_id": "TKT-OLD-1", "subject": "VPN auth failure after AD sync", "resolution": "Restart NPS service", "category": "network_issue"},
    {"ticket_id": "TKT-OLD-2", "subject": "Postgres replication lag causing writes to fail", "resolution": "Promoted replica", "category": "outage"},
]


@beta_tool
def search_knowledge_base(query: str, max_results: int = 3) -> str:
    """Search the internal knowledge base for relevant articles.

    Args:
        query: Free-text search query describing the issue.
        max_results: Maximum number of articles to return (1–10).
    """
    max_results = max(1, min(10, max_results))
    query_lower = query.lower()

    scored = []
    for article in _KB_ARTICLES:
        score = sum(1 for tag in article["tags"] if tag in query_lower)
        if any(word in article["title"].lower() for word in query_lower.split()):
            score += 2
        if score > 0:
            scored.append((score, article))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [a for _, a in scored[:max_results]]

    return json.dumps({"status": "ok", "data": {"articles": results, "total": len(results)}})


@beta_tool
def get_similar_tickets(description: str, max_results: int = 3) -> str:
    """Find past resolved tickets similar to the current issue.

    Args:
        description: The issue description to match against.
        max_results: Maximum number of similar tickets to return (1–5).
    """
    max_results = max(1, min(5, max_results))
    desc_lower = description.lower()

    scored = []
    for ticket in _PAST_TICKETS:
        words = set(ticket["subject"].lower().split())
        overlap = sum(1 for word in desc_lower.split() if word in words)
        if overlap > 0:
            scored.append((overlap, ticket))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [t for _, t in scored[:max_results]]

    return json.dumps({"status": "ok", "data": {"tickets": results, "total": len(results)}})
