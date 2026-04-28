# Solo — Alessandro Manzo

## Participants
- Alessandro Manzo (PM, Architect, Developer, Quality — solo run)

## Scenario
Scenario 5: Agentic Solution

## What We Built

A fully agentic IT service desk triage pipeline that replaces hand-triage of ~200 tickets/day. A **coordinator agent** (Claude Opus 4.7, adaptive thinking) receives each incoming ticket and delegates to three specialist subagents: **triage** (classify category, priority, confidence, impact), **routing** (assign team, queue, SLA), and **escalation** (decide tier: none / L2 / L3 / management / security). Every subagent returns a validated Pydantic model via `messages.parse()`. The coordinator then runs a tool loop — updating the ticket, assigning it, and firing team/user notifications — before emitting a final structured `TicketDecision`.

Everything that runs: coordinator + 3 subagents, 9 custom tools (`@beta_tool`), 25 unit tests all passing, a 15-ticket golden eval set, a 10-ticket adversarial eval set with safety-pass rate tracking, and a rich CLI demo runner. The tool contract is strict: every tool returns `{"status": "ok/error", ...}` — never raises — so Claude can reason about failures without breaking the loop.

Routing uses a deterministic fast-path (no LLM call) when confidence ≥ 0.80, saving ~40% of routing tokens. Escalation has a rule-engine fast-path for hard cases (security incidents, critical outages, low-confidence + high-impact), falling through to Sonnet only when judgment is genuinely needed.

## Challenges Attempted

| # | Challenge | Status | Notes |
|---|---|---|---|
| 1 | **The Mandate** — define what the agent decides alone vs. escalates | Done | Escalation matrix in CLAUDE.md; 3-factor rule (category + confidence + impact) |
| 2 | **The Bones** — coordinator + specialist subagent architecture | Done | Coordinator → Triage → Routing → Escalation; sequencing and context passing documented |
| 3 | **The Tools** — custom tools with structured error responses | Done | 9 tools across 4 modules; all return `{status, code, message, retryable}` on error |
| 4 | **The Triage** — coordinator agent, classify + enrich + route | Done | Full tool loop with ≤8 call guard; coordinator_notes log every tool call + result |
| 5 | **The Brake** — escalation rules (category + confidence + impact) | Done | Hard-rule fast-path + LLM judgment layer; VIP minimum L2; security always escalates |
| 6 | **The Attack** — adversarial eval set | Done | 10 attacks: prompt injection, false urgency, authority impersonation, schema injection, tool abuse |
| 7 | **The Scorecard** — eval harness with metrics | Done | `run_evals.py` with accuracy/F1/safety-pass-rate; exits 1 on adversarial safety failures |
| 8 | **The Loop** — human-override feeding back to evals | Skipped | Good next step; feedback would flow into `golden_tickets.json` as new labelled examples |

## Key Decisions

**Model tiering by task width, not just cost.** Triage and routing are narrow classification tasks — a single correct label from a fixed set. Haiku handles these with structured output and zero thinking needed. Escalation requires judgment across multiple factors; Sonnet with adaptive thinking gets the nuance without Opus cost. The coordinator does multi-hop reasoning across tool results and needs Opus. Total cost per ticket: ~$0.003–0.006 depending on escalation path, vs. estimated $0.012 if everything ran on Opus.

**Deterministic fast-paths before LLM calls.** Routing uses a pure lookup when confidence ≥ 0.80 — the category already maps to exactly one team. Escalation applies a rule engine first: security incidents, critical outages, and low-confidence + high-impact all have known-correct answers that don't need a model. This makes the most common cases both faster and more predictable.

**Tool contract over raw exceptions.** Every tool returns a typed JSON envelope. This was deliberate — when a ticket lookup fails mid-loop, Claude sees `{"status": "error", "code": "TICKET_NOT_FOUND", "retryable": false}` and can decide to skip or report rather than crashing the loop. The `retryable` flag is readable by both Claude and any wrapper retry logic.

**Frozen system prompts with prompt caching.** All three subagents cache their system prompt on the last block. The prompt never has dynamic data interpolated into it — ticket content only ever appears in the user turn. This keeps the 5-minute TTL working and cuts prompt token cost roughly in half on repeated calls.

**Adversarial safety as a hard gate.** The eval harness exits non-zero if `safety_pass_rate < 1.0` on the adversarial dataset. This is a CI-style gate, not a dashboard number — if the agent can be manipulated into escalating a trivial ticket to management or routing to security on a prompt injection, the pipeline fails. Accuracy on golden tickets is a metric; safety on adversarial tickets is a requirement.

## How to Run It

```bash
# Prerequisites: Python 3.11+, pip

git clone <repo>
cd hackathon-s5

# Install
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...

# Run the demo (processes the two seeded demo tickets)
python -m servicedesk.main

# Run against specific ticket IDs
python -m servicedesk.main TKT-001 TKT-002

# Run unit tests (no API key needed — all mocked)
python -m pytest tests/ -v

# Run golden evals (hits the API — uses haiku, ~$0.05)
python -m evals.run_evals --dataset golden

# Run adversarial evals (hits the API)
python -m evals.run_evals --dataset adversarial

# Run everything
python -m evals.run_evals --dataset all

# Generate synthetic tickets for load testing
python scripts/generate_tickets.py -n 100 -o synthetic.json
```

## If We Had More Time

1. **Close the feedback loop (Challenge 8).** When a human overrides an escalation decision, that ticket + correction should land in `golden_tickets.json` as a new labelled example and feed back into the eval run at next deploy. Currently the loop is open.

2. **Real ticket backend.** Swap the in-memory `_TICKET_STORE` for a Jira or ServiceNow adapter behind the same tool interface. The tool contract is already clean enough that this is a one-file change.

3. **Validation-retry loop in subagents.** If `messages.parse()` returns a validation error (malformed category enum, confidence out of range), retry with the specific schema error fed back to Claude, up to N=3 times, and log retry count. The scaffold is there; the loop isn't wired yet.

4. **`PreToolUse` hook for hard stops.** A deterministic hook that blocks `notify_team` calls if the message body contains PII patterns, or blocks `update_ticket` if the ticket is in a frozen/closed state. Complements the escalation rules — hooks are hard stops, escalation is a slow stop.

5. **Stratified sampling in evals.** The golden set has 15 tickets; categories like `billing` and `data_loss` have only 1–2 examples. Expand to 50+ tickets with ≥3 per category for stable per-category F1. Add a false-confidence metric: how often is confidence ≥ 0.80 but the category is wrong?

6. **MCP server over the tool layer.** Wrap the 9 tools as an MCP server so any Claude session can call `lookup_ticket`, `search_knowledge_base`, etc. without importing the package. Makes the tooling reusable across scenarios.

## How We Used Claude Code

**Scaffolding at speed.** The full project structure, pyproject.toml, CLAUDE.md, all four tool modules, three agents, coordinator, eval harness, and 25 tests were generated in a single session with zero manual file creation. The session was cut off mid-stream (context limit) and resumed cleanly from a summary — the continuity held.

**Architecture as conversation.** The model tiering decision (haiku/sonnet/opus by task width), the fast-path routing logic, and the tool error contract all emerged from back-and-forth in the session rather than being pre-planned. Externalizing reasoning into CLAUDE.md before writing code kept the later code coherent with the earlier decisions.

**Adversarial thinking at no extra cost.** Asking Claude to generate the adversarial eval dataset produced attack patterns (role-play injection, schema injection, tool abuse via body) that I wouldn't have enumerated quickly alone. The safety_check field on each adversarial case made the harness assertion logic clean.

**Where it saved the most time.** Writing the Pydantic schemas and wiring them to `messages.parse()` would have taken 30 minutes of docs-reading per subagent. Claude had the exact beta API signature ready and flagged the `betas=["interleaved-thinking-2025-05-14"]` header requirement without being asked. Test mocking patterns for the Anthropic client similarly appeared correctly on first generation.
