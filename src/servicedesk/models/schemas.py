from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Priority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class Impact(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EscalationTier(str, Enum):
    NONE = "none"
    L2 = "l2"
    L3 = "l3"
    MANAGEMENT = "management"
    SECURITY = "security"


class IncomingTicket(BaseModel):
    ticket_id: str
    subject: str
    body: str
    requester_id: str
    created_at: str


class UserInfo(BaseModel):
    user_id: str
    name: str
    email: str
    department: str
    is_vip: bool = False
    past_ticket_count: int = 0


class TriageResult(BaseModel):
    category: str = Field(description="One of the supported ticket categories")
    priority: Priority
    confidence: float = Field(ge=0.0, le=1.0, description="Model confidence 0–1")
    impact: Impact
    summary: str = Field(description="One-sentence summary of the ticket")
    tags: list[str] = Field(default_factory=list)


class RoutingResult(BaseModel):
    team_id: str
    queue: str
    sla_minutes: int = Field(gt=0)
    assignment_note: str


class EscalationResult(BaseModel):
    should_escalate: bool
    escalation_tier: EscalationTier
    reason: str
    notify_targets: list[str] = Field(
        default_factory=list,
        description="User IDs or team IDs to notify",
    )


class TicketDecision(BaseModel):
    ticket_id: str
    triage: TriageResult
    routing: RoutingResult
    escalation: EscalationResult
    coordinator_notes: Optional[str] = None


class ToolError(BaseModel):
    status: str = "error"
    code: str
    message: str
    retryable: bool = False
