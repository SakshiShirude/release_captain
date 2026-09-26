from uuid import uuid4

from typing import Union

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.models import ApprovalRequest, AuditEvent, ReleaseSession, SessionCreate, SessionStatus
from app.services.analysis_service import analyze
from app.services.github_service import collect
from app.services.execution_service import run

router = APIRouter(prefix="/api")
SESSIONS: dict[str, ReleaseSession] = {}


def event(action: str, status: str, detail: str) -> AuditEvent:
    return AuditEvent(action=action, status=status, detail=detail)


@router.get("/health")
async def health() -> dict[str, Union[str, bool]]:
    return {"status": "ok", "demo_mode": get_settings().demo_mode}


@router.post("/sessions", response_model=ReleaseSession, status_code=201)
async def create_session(request: SessionCreate) -> ReleaseSession:
    session = ReleaseSession(id=str(uuid4()), repository_url=str(request.repository_url), branch=request.branch, previous_tag=request.previous_tag, test_command=request.test_command, status=SessionStatus.collecting)
    session.audit.append(event("collect_repository", "started", f"Reading {session.repository_url}@{session.branch}"))
    try:
        session.commits, session.pull_requests = await collect(session.repository_url, session.branch, session.previous_tag)
        session.status = SessionStatus.analyzing
        session.audit.append(event("collect_repository", "completed", f"Collected {len(session.commits)} commits and {len(session.pull_requests)} pull requests"))
        session.plan = analyze(session.commits, session.previous_tag or "0.0.0")
        session.audit.append(event("analyze_release", "completed", f"Recommended {session.plan.recommended_version}"))
        session.status = SessionStatus.testing
        session.test_result = await run(session.test_command, get_settings().demo_mode)
        session.audit.append(event("run_tests", session.test_result.status, session.test_result.log_excerpt))
        session.status = SessionStatus.ready_for_approval
        session.audit.append(event("approval_gate", "waiting", "WAITING FOR HUMAN APPROVAL"))
    except (ValueError, RuntimeError) as exc:
        session.status = SessionStatus.failed
        session.audit.append(event("session", "failed", str(exc)))
    SESSIONS[session.id] = session
    return session


def get_session_or_404(session_id: str) -> ReleaseSession:
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/sessions/{session_id}", response_model=ReleaseSession)
async def get_session(session_id: str) -> ReleaseSession:
    return get_session_or_404(session_id)


@router.post("/sessions/{session_id}/approve", response_model=ReleaseSession)
async def approve_session(session_id: str, request: ApprovalRequest) -> ReleaseSession:
    session = get_session_or_404(session_id)
    if not session.plan or request.plan_version != session.plan.recommended_version or request.repository_url != session.repository_url or request.actions != session.plan.proposed_actions or not request.approved:
        raise HTTPException(status_code=409, detail="Approval does not match the exact release plan")
    session.approval = request
    session.status = SessionStatus.approved
    session.audit.append(event("approval", "approved", "Exact release plan approved by human"))
    return session


@router.post("/sessions/{session_id}/request-changes", response_model=ReleaseSession)
async def request_changes(session_id: str, request: dict[str, str]) -> ReleaseSession:
    session = get_session_or_404(session_id)
    session.status = SessionStatus.rejected
    session.audit.append(event("approval", "changes_requested", request.get("comment", "Changes requested")))
    return session


@router.get("/sessions/{session_id}/audit", response_model=list[AuditEvent])
async def audit(session_id: str) -> list[AuditEvent]:
    return get_session_or_404(session_id).audit


@router.get("/sessions/{session_id}/evidence")
async def evidence(session_id: str) -> dict:
    session = get_session_or_404(session_id)
    return {"commits": session.commits, "pull_requests": session.pull_requests, "test_result": session.test_result, "plan": session.plan}
