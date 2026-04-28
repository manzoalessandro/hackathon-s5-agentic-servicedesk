"""Synthetic ticket generator — creates N realistic tickets for load testing."""
from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timezone

TEMPLATES = [
    {
        "category": "network_issue",
        "subjects": [
            "VPN connection drops intermittently",
            "Cannot access internal resources from remote",
            "Slow network on floor {floor}",
        ],
        "bodies": [
            "Since {time}, my VPN drops every {n} minutes. Error: '{error}'.",
            "I cannot reach internal services from outside the office. No error shown.",
        ],
        "priority_range": ("P3", "P4"),
    },
    {
        "category": "outage",
        "subjects": [
            "CRITICAL: {service} is down",
            "{service} returning 500 for all users",
            "Production {service} unreachable",
        ],
        "bodies": [
            "All requests to {service} are failing since {time}. {n} users affected.",
            "{service} has been returning HTTP 503 for the last {n} minutes. Revenue impact confirmed.",
        ],
        "priority_range": ("P1", "P2"),
    },
    {
        "category": "access_request",
        "subjects": [
            "Request access to {system}",
            "New joiner needs {system} account",
            "Permission change for {system}",
        ],
        "bodies": [
            "Please grant me access to {system}. Manager approval attached.",
            "New team member {name} starts {date} and needs {system} provisioned.",
        ],
        "priority_range": ("P3", "P4"),
    },
    {
        "category": "security_incident",
        "subjects": [
            "Suspicious login attempt on my account",
            "Phishing email received from external sender",
            "Unusual process detected on workstation",
        ],
        "bodies": [
            "I received an alert for a login from {country} which I did not initiate.",
            "An email asked me to reset my password via an external link. I did not click it.",
        ],
        "priority_range": ("P1", "P2"),
    },
    {
        "category": "hardware_failure",
        "subjects": [
            "Laptop screen flickering",
            "Keyboard stopped working",
            "External monitor not detected",
        ],
        "bodies": [
            "My {device} stopped working after the latest OS update.",
            "The {device} on my desk has been intermittently failing for {n} days.",
        ],
        "priority_range": ("P3", "P4"),
    },
]

USERS = ["usr-42", "usr-07", "usr-99"]
SERVICES = ["auth-service", "payment-api", "data-warehouse", "hr-portal", "ci-cd-runner"]
SYSTEMS = ["Jira", "Confluence", "AWS console", "GitHub", "Salesforce"]
ERRORS = ["Connection timed out", "Authentication failed", "Service unavailable", "TLS handshake error"]
COUNTRIES = ["Russia", "China", "Brazil", "Nigeria", "Romania"]
DEVICES = ["laptop", "keyboard", "monitor", "trackpad", "USB hub"]
NAMES = ["Jordan Lee", "Sam Torres", "Morgan Kim", "Alex Chen", "Riley Park"]


def _fill(template: str) -> str:
    return template.format(
        floor=random.randint(1, 6),
        n=random.randint(2, 30),
        time=f"0{random.randint(6,9)}:{random.choice(['00','15','30','45'])}",
        service=random.choice(SERVICES),
        system=random.choice(SYSTEMS),
        error=random.choice(ERRORS),
        country=random.choice(COUNTRIES),
        device=random.choice(DEVICES),
        name=random.choice(NAMES),
        date="next Monday",
    )


def generate(n: int, seed: int = 42) -> list[dict]:
    random.seed(seed)
    tickets = []
    for i in range(n):
        tmpl = random.choice(TEMPLATES)
        subject = _fill(random.choice(tmpl["subjects"]))
        body = _fill(random.choice(tmpl["bodies"]))
        tickets.append({
            "ticket_id": f"SYNTH-{i+1:04d}",
            "subject": subject,
            "body": body,
            "requester_id": random.choice(USERS),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "_hint_category": tmpl["category"],
        })
    return tickets


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic tickets")
    parser.add_argument("-n", type=int, default=50, help="Number of tickets to generate")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("-o", "--output", default="synthetic_tickets.json")
    args = parser.parse_args()

    tickets = generate(args.n, args.seed)
    with open(args.output, "w") as f:
        json.dump(tickets, f, indent=2)
    print(f"Generated {len(tickets)} tickets → {args.output}")


if __name__ == "__main__":
    main()
