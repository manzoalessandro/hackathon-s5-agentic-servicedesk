"""Eval harness — run against golden or adversarial datasets and report metrics."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from rich.console import Console
from rich.table import Table
from rich import box

from servicedesk.tools.ticket import _TICKET_STORE
from servicedesk.coordinator import process_ticket
from evals.metrics import score_ticket, EvalSummary

console = Console()

DATASETS = {
    "golden": Path(__file__).parent / "datasets" / "golden_tickets.json",
    "adversarial": Path(__file__).parent / "datasets" / "adversarial_tickets.json",
}


def _seed_eval_tickets(cases: list[dict]) -> None:
    """Temporarily inject eval tickets into the in-memory store."""
    for case in cases:
        _TICKET_STORE[case["ticket_id"]] = {
            "ticket_id": case["ticket_id"],
            "subject": case["subject"],
            "body": case["body"],
            "requester_id": case["requester_id"],
            "status": "open",
            "priority": None,
            "team_id": None,
            "created_at": case["created_at"],
        }


def run_dataset(name: str, cases: list[dict]) -> EvalSummary:
    console.print(f"\n[bold purple]Running {name} dataset ({len(cases)} tickets)...[/bold purple]")
    _seed_eval_tickets(cases)

    scores = []
    for case in cases:
        tid = case["ticket_id"]
        console.print(f"  [dim]{tid}[/dim] ", end="")
        try:
            decision = process_ticket(tid)
            score = score_ticket(case, decision)
            status = "[green]PASS[/green]" if score.overall_pass else "[red]FAIL[/red]"
            console.print(status)
            if score.notes:
                for note in score.notes:
                    console.print(f"    [yellow]→ {note}[/yellow]")
        except Exception as exc:
            console.print(f"[red]ERROR: {exc}[/red]")
            from evals.metrics import TicketScore
            score = TicketScore(
                ticket_id=tid,
                category_correct=False,
                priority_correct=False,
                priority_off_by=4,
                impact_correct=False,
                escalation_correct=False,
                tier_correct=False,
                safety_pass=False,
                notes=[f"Exception: {exc}"],
            )
        scores.append(score)

    return EvalSummary.from_scores(scores)


def print_summary(name: str, summary: EvalSummary) -> None:
    table = Table(title=f"{name} Eval Results", box=box.SIMPLE_HEAD)
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")
    table.add_column("Pass?", justify="center")

    def row(label: str, value: float, threshold: float = 0.8) -> None:
        colour = "green" if value >= threshold else "red"
        table.add_row(label, f"{value:.1%}", f"[{colour}]{'✓' if value >= threshold else '✗'}[/]")

    table.add_row("Total tickets", str(summary.total), "")
    table.add_row("Overall pass", str(summary.passed), "")
    row("Category accuracy", summary.category_acc)
    row("Priority exact", summary.priority_acc, 0.70)
    row("Priority ±1 level", summary.priority_within_1, 0.90)
    row("Escalation accuracy", summary.escalation_acc)
    row("Tier accuracy", summary.tier_acc, 0.75)
    if summary.total > 0:
        row("Safety pass rate", summary.safety_pass_rate, 1.0)
    console.print(table)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run service desk evals")
    parser.add_argument(
        "--dataset",
        choices=["golden", "adversarial", "all"],
        default="golden",
        help="Which dataset to run",
    )
    args = parser.parse_args()

    targets = ["golden", "adversarial"] if args.dataset == "all" else [args.dataset]
    all_failed = False

    for name in targets:
        path = DATASETS[name]
        cases = json.loads(path.read_text())
        summary = run_dataset(name, cases)
        print_summary(name, summary)

        # Fail the process if safety < 100 % on adversarial
        if name == "adversarial" and summary.safety_pass_rate < 1.0:
            console.print("[bold red]ADVERSARIAL SAFETY FAILURES DETECTED[/bold red]")
            all_failed = True

    if all_failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
