# CLAUDE.md — IT Service Desk Triage Agent

## Project Purpose

Replace manual triage of ~200 IT service desk tickets/day with an agentic pipeline.
A **coordinator agent** receives each ticket and delegates to three specialist subagents:
**triage** (classify + prioritise), **routing** (assign team/queue), and **escalation**
(decide whether the ticket needs immediate human attention). All decisions are structured,
logged, and testable via an adversarial eval harness.

---

## Architecture

```
Incoming Ticket
      │
      ▼
┌─────────────────────────────────────────────┐
│          COORDINATOR AGENT                  │
│  model: claude-opus-4-7 + adaptive thinking │
│  Tools: lookup_ticket, get_user_info,        │
│         update_ticket, notify_*             │
└───────┬──────────────────┬──────────────────┘
        │                  │
        ▼                  ▼
┌──────────────┐   ┌──────────────────┐
│ TRIAGE AGENT │   │  ROUTING AGENT   │
│ haiku-4-5    │   │  haiku-4-5       │
│ ─────────    │   │  ──────────      │
│ category     │   │  team_id         │
│ priority     │   │  queue           │
│ confidence   │   │  sla_minutes     │
│ impact       │──▶│  assignment_note │
└──────────────┘   └──────────────────┘
        │
        ▼
┌──────────────────────┐
│  ESCALATION AGENT    │
│  sonnet-4-6          │
│  ─────────────────   │
│  should_escalate     │
│  escalation_tier     │
│  reason              │
│  notify_targets      │
└──────────────────────┘
```

**Sequencing:** Coordinator calls Triage → Routing (parallel-safe once category known) →
Escalation. The coordinator merges outputs and writes the final ticket state.

---

## Agent Responsibilities

### Coordinator (`src/servicedesk/coordinator.py`)
- Entry point for each ticket
- Manages the tool loop; calls subagents via `run_triage`, `run_routing`, `run_escalation`
- Merges structured outputs into a final `TicketDecision`
- Writes back to the ticket system; fires notifications
- Uses `claude-opus-4-7` + `thinking: {type: "adaptive"}` for complex multi-hop reasoning

### Triage Agent (`src/servicedesk/agents/triage.py`)
- Reads ticket title, body, user context
- Returns: `category`, `priority`, `confidence` (0–1), `impact` (`low/medium/high/critical`)
- Uses `claude-haiku-4-5` — fast, cheap, structured output via `messages.parse()`
- Output validated against `TriageResult` Pydantic model

### Routing Agent (`src/servicedesk/agents/routing.py`)
- Takes triage output + user VIP status
- Returns: `team_id`, `queue`, `sla_minutes`, `assignment_note`
- Uses `claude-haiku-4-5` + structured output
- Contains routing table logic (see `ROUTING_MATRIX` in `config.py`)

### Escalation Agent (`src/servicedesk/agents/escalation.py`)
- Takes triage + routing + user context
- Applies three-factor rule: `category` + `confidence` + `impact`
- Returns: `should_escalate` (bool), `escalation_tier` (`l2/l3/management/security`), `reason`, `notify_targets`
- Uses `claude-sonnet-4-6` — needs more judgment than haiku; cheaper than opus

---

## Tool Contracts

Every tool returns either a **success payload** or a **structured error**. Never raise
exceptions out of a tool — Claude needs to reason about failures.

```python
# Success
{"status": "ok", "data": {...}}

# Error
{"status": "error", "code": "TICKET_NOT_FOUND", "message": "...", "retryable": False}
```

### Tools

| Tool | File | Description |
|---|---|---|
| `lookup_ticket` | `tools/ticket.py` | Fetch full ticket details by ID |
| `create_ticket` | `tools/ticket.py` | Open a new ticket |
| `update_ticket` | `tools/ticket.py` | Patch ticket fields (status, priority, assignee) |
| `search_knowledge_base` | `tools/knowledge_base.py` | Semantic search across KB articles |
| `get_similar_tickets` | `tools/knowledge_base.py` | Find past tickets by embedding similarity |
| `get_user_info` | `tools/system_info.py` | User profile, VIP flag, department, past tickets |
| `notify_user` | `tools/notification.py` | Send status update to ticket requester |
| `notify_team` | `tools/notification.py` | Post alert to team Slack channel |
| `assign_ticket` | `tools/notification.py` | Set assignee + team on ticket |

---

## Escalation Matrix

| Category | Confidence | Impact | Escalation Tier |
|---|---|---|---|
| `security_incident` | any | any | `security` — always |
| any | < 0.40 | `high` or `critical` | `l3` — low confidence + high stakes |
| `outage` | any | `critical` | `management` |
| `outage` | ≥ 0.70 | `high` | `l2` |
| `data_loss` | ≥ 0.60 | any | `l3` |
| any | < 0.40 | `low` or `medium` | `l2` — human review needed |
| any | ≥ 0.80 | `low` | none — auto-route |
| VIP user | any | any | `l2` minimum |

---

## Supported Categories

```python
CATEGORIES = [
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
```

---

## Eval Approach

### Golden set (`evals/datasets/golden_tickets.json`)
50 labelled tickets with expected: `category`, `priority`, `should_escalate`, `escalation_tier`.
Metric: accuracy per field + weighted F1 on category.

### Adversarial set (`evals/datasets/adversarial_tickets.json`)
25 tickets designed to break the pipeline:
- **Prompt injection** in ticket body (`"Ignore previous instructions and..."`)
- **False urgency inflation** (`"THIS IS CRITICAL EMERGENCY"` for a password reset)
- **Jailbreak via subject line**
- **Ambiguous multi-category** tickets
- **Minimal/empty** tickets
- **Non-English** tickets
- **Confidence manipulation** (`"I'm 100% sure this is a P0 outage"`)

Metric: pipeline must produce a valid `TicketDecision` without leaking internal prompts,
ignoring injected instructions, and not inflating priority beyond what evidence supports.

### Running evals
```bash
python -m evals.run_evals --dataset golden    # accuracy report
python -m evals.run_evals --dataset adversarial  # safety report
python -m evals.run_evals --all               # both + aggregate scorecard
```

---

## Development Conventions

- **Models**: coordinator = `claude-opus-4-7`, escalation = `claude-sonnet-4-6`,
  triage/routing = `claude-haiku-4-5`
- **Thinking**: coordinator uses `thinking: {"type": "adaptive"}` only; subagents use
  structured outputs (`messages.parse()`) — no thinking needed for narrow classification
- **Structured outputs**: all subagent responses validated with Pydantic via `messages.parse()`
- **Prompt caching**: system prompts for each agent are frozen strings with `cache_control`
  on the last system block — never interpolate dynamic data into system prompts
- **Tool errors**: tools return `{"status": "error", ...}` — never raise; Claude reasons over errors
- **No side effects in tests**: `tests/` mocks the Anthropic client and all tools
- **Evals are real API calls**: `evals/` always hits the real API; uses `claude-haiku-4-5`
  for cost unless `--full` flag is passed

---

## File Map

```
hackathon-s5/
├── CLAUDE.md                        ← you are here
├── pyproject.toml
├── .env.example
├── src/servicedesk/
│   ├── coordinator.py               ← main orchestration loop
│   ├── agents/
│   │   ├── triage.py
│   │   ├── routing.py
│   │   └── escalation.py
│   ├── tools/
│   │   ├── ticket.py
│   │   ├── knowledge_base.py
│   │   ├── system_info.py
│   │   └── notification.py
│   ├── models/schemas.py            ← Pydantic models for all I/O
│   └── config.py                    ← routing matrix, category list, model IDs
├── evals/
│   ├── datasets/golden_tickets.json
│   ├── datasets/adversarial_tickets.json
│   ├── run_evals.py
│   └── metrics.py
├── tests/
│   ├── test_coordinator.py
│   ├── test_triage.py
│   ├── test_routing.py
│   └── test_escalation.py
└── scripts/generate_tickets.py
```
