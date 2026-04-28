from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Issue, Member, Runtime, Task, TaskEvent, Workspace
from .schemas import (
    IssueAssign,
    IssueCreate,
    IssueRead,
    MemberCreate,
    MemberRead,
    RuntimeClaim,
    RuntimeHeartbeat,
    RuntimeRegister,
    RuntimeReport,
    TaskRead,
    WorkspaceCreate,
    WorkspaceRead,
)

app = FastAPI(title="Multi-Agent P0 API", version="0.1.0")
Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/workspaces", response_model=WorkspaceRead)
def create_workspace(payload: WorkspaceCreate, db: Session = Depends(get_db)):
    workspace = Workspace(name=payload.name)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


@app.post("/api/members", response_model=MemberRead)
def create_member(payload: MemberCreate, db: Session = Depends(get_db)):
    workspace = db.get(Workspace, payload.workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    member = Member(
        workspace_id=payload.workspace_id,
        user_id=payload.user_id,
        role=payload.role,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@app.post("/api/issues", response_model=IssueRead)
def create_issue(payload: IssueCreate, db: Session = Depends(get_db)):
    workspace = db.get(Workspace, payload.workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    issue = Issue(
        workspace_id=payload.workspace_id,
        title=payload.title,
        description=payload.description,
        status="todo",
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue


@app.get("/api/issues", response_model=list[IssueRead])
def list_issues(workspace_id: int, db: Session = Depends(get_db)):
    rows = db.scalars(select(Issue).where(Issue.workspace_id == workspace_id).order_by(Issue.updated_at.desc())).all()
    return rows


@app.get("/api/issues/{issue_id}", response_model=IssueRead)
def get_issue(issue_id: int, db: Session = Depends(get_db)):
    issue = db.get(Issue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue


@app.post("/api/issues/{issue_id}/assign", response_model=TaskRead)
def assign_issue(issue_id: int, payload: IssueAssign, db: Session = Depends(get_db)):
    issue = db.get(Issue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    issue.assignee_type = payload.assignee_type
    issue.assignee_id = payload.assignee_id
    issue.status = "in_progress"
    issue.updated_at = datetime.utcnow()

    task = Task(
        workspace_id=issue.workspace_id,
        issue_id=issue.id,
        agent_id=payload.assignee_id if payload.assignee_type == "agent" else None,
        status="queued",
        priority=payload.priority,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@app.post("/api/runtimes/register")
def register_runtime(payload: RuntimeRegister, db: Session = Depends(get_db)):
    workspace = db.get(Workspace, payload.workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    runtime = Runtime(
        workspace_id=payload.workspace_id,
        name=payload.name,
        capabilities_json=payload.capabilities_json,
    )
    db.add(runtime)
    db.commit()
    db.refresh(runtime)
    return {"runtime_id": runtime.id}


@app.post("/api/runtimes/{runtime_id}/heartbeat")
def heartbeat_runtime(runtime_id: int, payload: RuntimeHeartbeat, db: Session = Depends(get_db)):
    runtime = db.get(Runtime, runtime_id)
    if not runtime:
        raise HTTPException(status_code=404, detail="Runtime not found")

    runtime.health = payload.health
    runtime.last_seen_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@app.post("/api/runtimes/{runtime_id}/claim", response_model=TaskRead)
def claim_task(runtime_id: int, payload: RuntimeClaim, db: Session = Depends(get_db)):
    runtime = db.get(Runtime, runtime_id)
    if not runtime:
        raise HTTPException(status_code=404, detail="Runtime not found")

    task = db.scalars(
        select(Task)
        .where(Task.workspace_id == payload.workspace_id, Task.status == "queued")
        .order_by(Task.priority.asc(), Task.queued_at.asc())
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="No queued task")

    task.runtime_id = runtime_id
    task.status = "running"
    task.started_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task


@app.post("/api/runtimes/{runtime_id}/report")
def report_task(runtime_id: int, payload: RuntimeReport, db: Session = Depends(get_db)):
    runtime = db.get(Runtime, runtime_id)
    if not runtime:
        raise HTTPException(status_code=404, detail="Runtime not found")

    task = db.get(Task, payload.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.runtime_id != runtime_id:
        raise HTTPException(status_code=409, detail="Task not claimed by this runtime")

    event = TaskEvent(
        workspace_id=task.workspace_id,
        task_id=task.id,
        event_type=payload.event_type,
        payload_json=payload.payload_json,
    )
    db.add(event)

    if payload.status:
        task.status = payload.status
        if payload.status in {"done", "failed", "blocked"}:
            task.finished_at = datetime.utcnow()
            issue = db.get(Issue, task.issue_id)
            if issue:
                issue.status = "done" if payload.status == "done" else payload.status
                issue.updated_at = datetime.utcnow()

    db.commit()
    return {"ok": True}


@app.get("/api/tasks/{task_id}/events")
def list_task_events(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    events = db.scalars(select(TaskEvent).where(TaskEvent.task_id == task_id).order_by(TaskEvent.created_at.asc())).all()
    return [
        {
            "id": evt.id,
            "event_type": evt.event_type,
            "payload_json": evt.payload_json,
            "created_at": evt.created_at,
        }
        for evt in events
    ]
