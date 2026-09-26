from uuid import uuid4

from typing import Union

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.models import ApprovalRequest, AuditEvent, ReleaseSession, SessionCreate, SessionStatus
from app.services.analysis_service import analyze
from app.services.github_service import collect
from app.services.execution_service import run
from app.services.release_service import approve, build_proposed_actions, execute_approved_plan

router = APIRouter(prefix="/api")
SESSIONS: dict[str, ReleaseSession] = {}


def event(action: str, status: str, detail: str) -> AuditEvent:
    return AuditEvent(action=action, status=status, detail=detail)


@router.get("/health")
async def health() -> dict[str, Union[str, bool]]:
    settings = get_settings()
    return {
        "status": "ok",
        "demo_mode": settings.demo_mode,
        "sandbox_enabled": settings.sandbox_enabled,
        "execution_enabled": settings.execution_enabled,
        "local_test_runner_enabled": settings.local_test_runner_enabled,
        "analysis_only": not settings.sandbox_enabled,
    }


@router.post("/sessions", response_model=ReleaseSession, status_code=201)
async def create_session(request: SessionCreate) -> ReleaseSession:
    settings = get_settings()
    session = ReleaseSession(
        id=str(uuid4()),
        repository_url=str(request.repository_url),
        branch=request.branch,
        previous_tag=request.previous_tag,
        test_command=request.test_command,
        analysis_only=not settings.sandbox_enabled,
        sandbox_enabled=settings.sandbox_enabled,
        status=SessionStatus.collecting,
    )
    session.audit.append(event("collect_repository", "started", f"Reading {session.repository_url}@{session.branch}"))
    try:
        session.commits, session.pull_requests, session.evidence = await collect(
            session.repository_url,
            session.branch,
            session.previous_tag,
            demo_mode=settings.demo_mode,
            github_token=settings.github_token,
            request_timeout_seconds=settings.request_timeout_seconds,
        )
        session.status = SessionStatus.analyzing
        session.audit.append(
            event(
                "collect_repository",
                "completed",
                f"Collected {len(session.commits)} commits, {len(session.pull_requests)} pull requests, and {len(session.evidence.get('changed_files', []))} changed files",
            )
        )
        session.plan = analyze(
            session.commits,
            session.evidence.get("current_version") or session.previous_tag or "0.0.0",
            changed_files=session.evidence.get("changed_files"),
            ci_runs=session.evidence.get("ci_runs"),
        )
        session.plan.proposed_actions = build_proposed_actions(
            recommended_version=session.plan.recommended_version,
            evidence_source=session.evidence.get("source"),
            demo_mode=settings.demo_mode,
        )
        session.audit.append(event("analyze_release", "completed", f"Recommended {session.plan.recommended_version}"))
        session.status = SessionStatus.testing
        session.test_result = await run(
            session.test_command,
            demo_mode=settings.demo_mode,
            sandbox_enabled=settings.sandbox_enabled,
            repository_url=session.repository_url,
            branch=session.branch,
            timeout_seconds=settings.test_timeout_seconds,
            local_test_runner_enabled=settings.local_test_runner_enabled,
        )
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
    settings = get_settings()
    session = get_session_or_404(session_id)
    if not session.plan or request.plan_version != session.plan.recommended_version or request.repository_url != session.repository_url or request.actions != session.plan.proposed_actions or not request.approved:
        raise HTTPException(status_code=409, detail="Approval does not match the exact release plan")
    session.approval = request
    try:
        approve(session)
        await execute_approved_plan(
            session,
            demo_mode=settings.demo_mode,
            execution_enabled=settings.execution_enabled,
            github_token=settings.github_token,
            request_timeout_seconds=settings.request_timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
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
    return {
        "commits": session.commits,
        "pull_requests": session.pull_requests,
        "test_result": session.test_result,
        "plan": session.plan,
        "evidence": session.evidence,
    }
