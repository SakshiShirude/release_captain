from __future__ import annotations

import asyncio

from app.models import AuditEvent, ReleaseSession, SessionStatus
from app.services.github_service import create_release_artifacts


def _event(action: str, status: str, detail: str) -> AuditEvent:
    return AuditEvent(action=action, status=status, detail=detail)


def approve(session: ReleaseSession) -> ReleaseSession:
    if session.status != SessionStatus.ready_for_approval:
        raise ValueError("Only a release plan waiting for approval can be approved")
    session.status = SessionStatus.approved
    session.audit.append(_event("approval", "approved", "Exact release plan approved by human"))
    return session


def build_proposed_actions(
    *,
    recommended_version: str,
    evidence_source: str | None,
    demo_mode: bool,
) -> list[str]:
    if evidence_source == "github":
        actions = [f"Create tag {recommended_version}", f"Create GitHub release {recommended_version}"]
        if demo_mode:
            actions.extend(["Publish release artifacts", "Trigger deployment"])
        return actions
    return [f"Create tag {recommended_version}", "Publish release artifacts", "Trigger deployment"]


async def execute_approved_plan(
    session: ReleaseSession,
    *,
    demo_mode: bool,
    execution_enabled: bool,
    github_token: str | None = None,
    request_timeout_seconds: float = 20.0,
) -> ReleaseSession:
    if session.status != SessionStatus.approved:
        raise ValueError("Only an approved release plan can be executed")
    if not session.plan:
        raise ValueError("Approved release plan is missing execution details")

    if demo_mode:
        session.status = SessionStatus.executing
        session.audit.append(_event("execute_release", "started", "Simulating approved release actions in demo mode"))
        for action in session.plan.proposed_actions:
            session.audit.append(_event("execute_action", "started", action))
            await asyncio.sleep(0)
            session.audit.append(_event("execute_action", "completed", action))
        session.status = SessionStatus.completed
        session.audit.append(_event("execute_release", "completed", "Demo release execution completed"))
        return session

    if not execution_enabled:
        session.audit.append(
            _event(
                "execute_release",
                "blocked",
                "Execution remains blocked because real post-approval actions are not enabled in this environment",
            )
        )
        return session

    if session.evidence.get("source") != "github":
        session.audit.append(_event("execute_release", "blocked", "Real execution currently supports GitHub-backed release plans only"))
        return session
    if not github_token:
        session.audit.append(_event("execute_release", "blocked", "GITHUB_TOKEN is required for real release execution"))
        return session

    session.status = SessionStatus.executing
    session.audit.append(_event("execute_release", "started", "Executing approved GitHub release actions"))
    results = await create_release_artifacts(
        session.repository_url,
        branch=session.branch,
        version=session.plan.recommended_version,
        release_notes=session.plan.release_notes,
        github_token=github_token,
        request_timeout_seconds=request_timeout_seconds,
        head_sha=session.evidence.get("head_sha"),
    )
    for result in results:
        session.audit.append(_event("execute_action", result["status"], f"{result['action']}: {result['detail']}"))
    session.status = SessionStatus.completed
    session.audit.append(_event("execute_release", "completed", "GitHub release actions completed"))
    return session
