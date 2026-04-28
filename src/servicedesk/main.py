"""Demo runner — processes all seeded demo tickets and prints a rich summary."""
from __future__ import annotations

import sys
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

load_dotenv()

from servicedesk.coordinator import process_ticket
from servicedesk.tools.ticket import _TICKET_STORE

console = Console()


def _priority_colour(priority: str) -> str:
    return {"P1": "bold red", "P2": "red", "P3": "yellow", "P4": "green"}.get(priority, "white")


def _escalation_colour(tier: str) -> str:
    return {
        "none": "green",
        "l2": "yellow",
        "l3": "orange3",
        "management": "red",
        "security": "bold red",
    }.get(tier, "white")


def run_demo(ticket_ids: list[str]) -> None:
    console.print(Panel("[bold purple]IT Service Desk — Agentic Pipeline[/bold purple]", expand=False))

    for tid in ticket_ids:
        console.print(f"\n[dim]Processing {tid}...[/dim]")
        try:
            decision = process_ticket(tid)
        except Exception as exc:
            console.print(f"[red]ERROR processing {tid}: {exc}[/red]")
            continue

        t = decision.triage
        r = decision.routing
        e = decision.escalation

        table = Table(box=box.SIMPLE_HEAD, show_header=False, padding=(0, 1))
        table.add_column("Field", style="dim", width=18)
        table.add_column("Value")

        table.add_row("Ticket", f"[bold]{decision.ticket_id}[/bold]")
        table.add_row("Category", t.category)
        table.add_row("Priority", f"[{_priority_colour(t.priority)}]{t.priority}[/]")
        table.add_row("Impact", t.impact)
        table.add_row("Confidence", f"{t.confidence:.0%}")
        table.add_row("Summary", t.summary)
        table.add_row("Tags", ", ".join(t.tags) or "—")
        table.add_row("", "")
        table.add_row("Team", r.team_id)
        table.add_row("Queue", r.queue)
        table.add_row("SLA", f"{r.sla_minutes} min")
        table.add_row("", "")
        esc_tier = e.escalation_tier if isinstance(e.escalation_tier, str) else e.escalation_tier.value
        table.add_row(
            "Escalation",
            f"[{_escalation_colour(esc_tier)}]{esc_tier.upper()}[/]"
            + (" ✓" if e.should_escalate else ""),
        )
        table.add_row("Reason", e.reason)
        if e.notify_targets:
            table.add_row("Notify", ", ".join(e.notify_targets))
        if decision.coordinator_notes:
            table.add_row("", "")
            table.add_row("Actions", decision.coordinator_notes[:200])

        console.print(Panel(table, title=f"[bold]{tid}[/bold]", border_style="purple"))

    console.print("\n[bold green]Pipeline complete.[/bold green]")


def main() -> None:
    ticket_ids = sys.argv[1:] if len(sys.argv) > 1 else list(_TICKET_STORE.keys())
    run_demo(ticket_ids)


if __name__ == "__main__":
    main()
