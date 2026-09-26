from uuid import uuid4

from typing import Union

import httpx

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.models import (
    ApprovalRequest,
    AuditEvent,
    ChangeRequest,
    ObservedToolCall,
    ReleaseSession,
    RepositoryMetadata,
    SessionCreate,
    SessionStatus,
    SessionSummary,
)
from app.services.analysis_service import analyze
from app.services.execution_service import run, unavailable_result
from app.services.github_service import GitHubCollectionError, collect, inspect_repository_metadata
from app.services.release_service import approve, build_proposed_actions, execute_approved_plan

router = APIRouter(prefix="/api")
SESSIONS: dict[str, ReleaseSession] = {}


def event(action: str, status: str, detail: str) -> AuditEvent:
    return AuditEvent(action=action, status=status, detail=detail)


def _refresh_summary(session: ReleaseSession) -> None:
    session.summary = SessionSummary(
        commit_count=len(session.commits),
        pull_request_count=len(session.pull_requests),
        changed_file_count=len(session.evidence.get("changed_files", [])),
        ci_run_count=len(session.evidence.get("ci_runs", [])),
        risk_count=len(session.plan.risks) if session.plan else 0,
        executed_action_count=len(session.execution_results),
        baseline=session.evidence.get("base_ref") or session.previous_tag,
        baseline_reason=session.evidence.get("baseline_reason"),
        latest_error=next((item.detail for item in reversed(session.audit) if item.status == "failed"), None)
        if session.status == SessionStatus.failed
        else None,
    )


def _reset_session_state(session: ReleaseSession, settings) -> None:
    session.analysis_only = not settings.sandbox_enabled
    session.sandbox_enabled = settings.sandbox_enabled
    session.status = SessionStatus.collecting
    session.commits = []
    session.pull_requests = []
    session.observed_tool_calls = []
    session.test_result = None
    session.plan = None
    session.approval = None
    session.execution_results = []
    session.evidence = {}
    session.summary = SessionSummary()


async def _run_release_workflow(session: ReleaseSession, settings) -> ReleaseSession:
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
        observed_tool_calls = session.evidence.pop("observed_tool_calls", [])
        session.observed_tool_calls = [ObservedToolCall.model_validate(item) for item in observed_tool_calls]
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
        if session.test_command:
            session.test_result = await run(
                session.test_command,
                demo_mode=settings.demo_mode,
                sandbox_enabled=settings.sandbox_enabled,
                repository_url=session.repository_url,
                branch=session.branch,
                timeout_seconds=settings.test_timeout_seconds,
                local_test_runner_enabled=settings.local_test_runner_enabled,
            )
        else:
            session.test_result = unavailable_result(
                "Not configured",
                "No allowlisted test command was detected; tests were not run.",
            )
        session.audit.append(event("run_tests", session.test_result.status, session.test_result.log_excerpt))
        session.status = SessionStatus.ready_for_approval
        session.audit.append(event("approval_gate", "waiting", "WAITING FOR HUMAN APPROVAL"))
    except GitHubCollectionError as exc:
        session.observed_tool_calls = [ObservedToolCall.model_validate(item) for item in exc.observed_calls]
        session.status = SessionStatus.failed
        session.audit.append(event("session", "failed", str(exc)))
    except (ValueError, RuntimeError) as exc:
        session.status = SessionStatus.failed
        session.audit.append(event("session", "failed", str(exc)))
    except httpx.HTTPError as exc:
        session.status = SessionStatus.failed
        session.audit.append(event("session", "failed", f"GitHub request failed: {str(exc)[:400]}"))
    _refresh_summary(session)
    return session


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


@router.get("/repository-metadata", response_model=RepositoryMetadata)
async def repository_metadata(repository_url: str) -> RepositoryMetadata:
    settings = get_settings()
    try:
        return await inspect_repository_metadata(
            repository_url,
            demo_mode=settings.demo_mode,
            github_token=settings.github_token,
            request_timeout_seconds=settings.request_timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="GitHub could not return repository metadata.") from exc


@router.get("/sessions", response_model=list[ReleaseSession])
async def list_sessions() -> list[ReleaseSession]:
    return list(SESSIONS.values())


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
    await _run_release_workflow(session, settings)
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


@router.post("/sessions/{session_id}/rerun", response_model=ReleaseSession)
async def rerun_session(session_id: str) -> ReleaseSession:
    settings = get_settings()
    session = get_session_or_404(session_id)
    session.audit.append(event("session", "restarted", "Re-running release analysis with the same input"))
    _reset_session_state(session, settings)
    await _run_release_workflow(session, settings)
    return session


@router.post("/sessions/{session_id}/approve", response_model=ReleaseSession)
async def approve_session(session_id: str, request: ApprovalRequest) -> ReleaseSession:
    settings = get_settings()
    session = get_session_or_404(session_id)
    if (
        not session.plan
        or request.plan_version != session.plan.recommended_version
        or request.repository_url != session.repository_url
        or request.actions != session.plan.proposed_actions
        or not request.approved
    ):
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
    except (RuntimeError, httpx.HTTPError) as exc:
        session.status = SessionStatus.failed
        session.audit.append(event("execute_release", "failed", str(exc)[:500]))
    _refresh_summary(session)
    return session


@router.post("/sessions/{session_id}/request-changes", response_model=ReleaseSession)
async def request_changes(session_id: str, request: ChangeRequest) -> ReleaseSession:
    session = get_session_or_404(session_id)
    session.status = SessionStatus.rejected
    session.audit.append(event("approval", "changes_requested", request.comment))
    _refresh_summary(session)
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
