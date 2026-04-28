from __future__ import annotations

import os

# ── AWS / Bedrock ─────────────────────────────────────────────────────────────
AWS_PROFILE = os.getenv("AWS_PROFILE", "bootcamp")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# ── Models (Bedrock cross-region inference profile IDs) ───────────────────────
COORDINATOR_MODEL = os.getenv("COORDINATOR_MODEL", "us.anthropic.claude-opus-4-7")
TRIAGE_MODEL      = os.getenv("TRIAGE_MODEL",      "us.anthropic.claude-haiku-4-5-20251001-v1:0")
ROUTING_MODEL     = os.getenv("ROUTING_MODEL",     "us.anthropic.claude-haiku-4-5-20251001-v1:0")
ESCALATION_MODEL  = os.getenv("ESCALATION_MODEL",  "us.anthropic.claude-sonnet-4-6")

# ── Supported categories ──────────────────────────────────────────────────────
CATEGORIES: list[str] = [
    "access_request",
    "hardware_failure",
    "software_bug",
    "network_issue",
    "security_incident",
    "outage",
    "data_loss",
    "performance_degradation",
    "provisioning",
    "billing",
    "other",
]

# ── Routing matrix ────────────────────────────────────────────────────────────
# Maps category → (team_id, queue, sla_minutes)
ROUTING_MATRIX: dict[str, tuple[str, str, int]] = {
    "access_request":          ("team-iam",      "iam-queue",      480),
    "hardware_failure":        ("team-hardware",  "hw-queue",       240),
    "software_bug":            ("team-appops",    "bug-queue",      480),
    "network_issue":           ("team-netops",    "network-queue",  120),
    "security_incident":       ("team-security",  "sec-queue",       30),
    "outage":                  ("team-sre",       "incident-queue",  15),
    "data_loss":               ("team-dataops",   "dataloss-queue",  60),
    "performance_degradation": ("team-sre",       "perf-queue",     120),
    "provisioning":            ("team-iam",       "prov-queue",     480),
    "billing":                 ("team-finance",   "billing-queue",  960),
    "other":                   ("team-general",   "general-queue",  960),
}

# ── Escalation thresholds ─────────────────────────────────────────────────────
LOW_CONFIDENCE_THRESHOLD = 0.40   # below this → always escalate to at least L2
AUTO_ROUTE_CONFIDENCE = 0.80      # above this + low impact → no escalation needed
