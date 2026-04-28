"""FastAPI web demo — streams the IT Service Desk pipeline via Server-Sent Events."""
from __future__ import annotations

import asyncio
import datetime as dt
import json
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

load_dotenv()

from servicedesk.coordinator import _run_coordinator_loop
from servicedesk.agents.triage import run_triage
from servicedesk.agents.routing import run_routing
from servicedesk.agents.escalation import run_escalation
from servicedesk.models.schemas import IncomingTicket, UserInfo
from servicedesk.tools.ticket import create_ticket
from servicedesk.tools.system_info import get_user_info, _USER_DB

app = FastAPI(title="IT Service Desk Agent")

_STATIC = Path(__file__).parent / "static"


class TicketRequest(BaseModel):
    requester_id: str
    subject: str
    body: str


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


@app.get("/")
async def index() -> HTMLResponse:
    html = (_STATIC / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/api/users")
async def list_users() -> list[dict]:
    return list(_USER_DB.values())


@app.post("/api/process")
async def process_stream(req: TicketRequest) -> StreamingResponse:
    async def generate():
        # Create ticket in the in-memory store
        raw = json.loads(create_ticket(req.subject, req.body, req.requester_id))
        ticket_id = raw["data"]["ticket_id"]

        ticket = IncomingTicket(
            ticket_id=ticket_id,
            subject=req.subject,
            body=req.body,
            requester_id=req.requester_id,
            created_at=dt.datetime.now(dt.UTC).isoformat(),
        )

        # Resolve user
        raw_user = json.loads(get_user_info(req.requester_id))
        if raw_user["status"] == "ok":
            user = UserInfo(**raw_user["data"])
        else:
            user = UserInfo(
                user_id=req.requester_id,
                name="Unknown",
                email="",
                department="Unknown",
            )

        yield _sse({
            "stage": "created",
            "ticket_id": ticket_id,
            "user": {
                "name": user.name,
                "is_vip": user.is_vip,
                "department": user.department,
            },
        })

        # Triage
        yield _sse({"stage": "triage", "status": "running"})
        try:
            triage = await asyncio.to_thread(run_triage, ticket, user)
            yield _sse({"stage": "triage", "status": "done", "result": triage.model_dump(mode="json")})
        except Exception as exc:
            yield _sse({"stage": "triage", "status": "error", "error": str(exc)})
            return

        # Routing
        yield _sse({"stage": "routing", "status": "running"})
        try:
            routing = await asyncio.to_thread(run_routing, triage)
            yield _sse({"stage": "routing", "status": "done", "result": routing.model_dump(mode="json")})
        except Exception as exc:
            yield _sse({"stage": "routing", "status": "error", "error": str(exc)})
            return

        # Escalation
        yield _sse({"stage": "escalation", "status": "running"})
        try:
            escalation = await asyncio.to_thread(run_escalation, ticket, user, triage, routing)
            yield _sse({"stage": "escalation", "status": "done", "result": escalation.model_dump(mode="json")})
        except Exception as exc:
            yield _sse({"stage": "escalation", "status": "error", "error": str(exc)})
            return

        # Coordinator tool loop
        yield _sse({"stage": "coordinator", "status": "running"})
        try:
            notes = await asyncio.to_thread(
                _run_coordinator_loop, ticket, user, triage, routing, escalation
            )
            yield _sse({"stage": "coordinator", "status": "done", "result": {"notes": notes}})
        except Exception as exc:
            yield _sse({"stage": "coordinator", "status": "error", "error": str(exc)})
            return

        yield _sse({"stage": "complete"})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
