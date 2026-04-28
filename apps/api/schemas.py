from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class WorkspaceRead(BaseModel):
    id: int
    name: str
    created_at: datetime

    class Config:
        from_attributes = True


class MemberCreate(BaseModel):
    workspace_id: int
    user_id: str
    role: str = Field(pattern="^(admin|member|viewer)$")


class MemberRead(BaseModel):
    id: int
    workspace_id: int
    user_id: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class IssueCreate(BaseModel):
    workspace_id: int
    title: str
    description: str = ""


class IssueAssign(BaseModel):
    assignee_type: str = Field(pattern="^(member|agent)$")
    assignee_id: int
    priority: int = 50


class IssueRead(BaseModel):
    id: int
    workspace_id: int
    title: str
    description: str
    status: str
    assignee_type: str | None
    assignee_id: int | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskRead(BaseModel):
    id: int
    workspace_id: int
    issue_id: int
    agent_id: int | None
    runtime_id: int | None
    status: str
    priority: int
    retry_count: int
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    class Config:
        from_attributes = True


class RuntimeRegister(BaseModel):
    workspace_id: int
    name: str
    capabilities_json: dict[str, Any] | None = None


class RuntimeHeartbeat(BaseModel):
    health: str = Field(default="healthy")


class RuntimeClaim(BaseModel):
    workspace_id: int


class RuntimeReport(BaseModel):
    task_id: int
    event_type: str = Field(pattern="^(log|progress|status|result|error)$")
    payload_json: dict[str, Any] | None = None
    status: str | None = Field(default=None, pattern="^(running|blocked|done|failed)$")
