from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, HttpUrl


def now() -> datetime:
    return datetime.now(timezone.utc)


class SessionStatus(str, Enum):
    created = "created"
    collecting = "collecting"
    analyzing = "analyzing"
    testing = "testing"
    ready_for_approval = "ready_for_approval"
    approved = "approved"
    executing = "executing"
    completed = "completed"
    rejected = "rejected"
    failed = "failed"


class CommitChange(BaseModel):
    sha: str
    message: str
    author: str
    category: str
    breaking: bool = False


class PullRequestChange(BaseModel):
    number: int
    title: str
    author: str
    labels: list[str] = Field(default_factory=list)
    merged: bool = True


class TestResult(BaseModel):
    command: str
    status: str
    exit_code: int
    duration_seconds: float
    passed_count: Optional[int] = None
    failed_count: Optional[int] = None
    log_excerpt: str
    sandbox_provider: str


class Risk(BaseModel):
    title: str
    severity: str
    evidence: list[str] = Field(default_factory=list)


class ReleasePlan(BaseModel):
    current_version: str = "0.0.0"
    recommended_version: str
    bump: str
    summary: str
    categories: dict[str, list[str]] = Field(default_factory=dict)
    breaking_changes: list[str] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    release_notes: str
    proposed_actions: list[str]


class ExecutionActionResult(BaseModel):
    action: str
    status: str
    detail: str


class SessionSummary(BaseModel):
    commit_count: int = 0
    pull_request_count: int = 0
    changed_file_count: int = 0
    ci_run_count: int = 0
    risk_count: int = 0
    executed_action_count: int = 0
    baseline: Optional[str] = None
    baseline_reason: Optional[str] = None
    latest_error: Optional[str] = None


class ApprovalRequest(BaseModel):
    approved: bool
    plan_version: str
    repository_url: str
    actions: list[str]
    comment: Optional[str] = None


class AuditEvent(BaseModel):
    timestamp: datetime = Field(default_factory=now)
    action: str
    status: str
    detail: str


class SessionCreate(BaseModel):
    repository_url: HttpUrl
    branch: str = "main"
    previous_tag: Optional[str] = None
    test_command: str = "pytest"


class ReleaseSession(BaseModel):
    id: str
    repository_url: str
    branch: str
    previous_tag: Optional[str]
    test_command: str
    analysis_only: bool = True
    sandbox_enabled: bool = False
    status: SessionStatus
    created_at: datetime = Field(default_factory=now)
    commits: list[CommitChange] = Field(default_factory=list)
    pull_requests: list[PullRequestChange] = Field(default_factory=list)
    test_result: Optional[TestResult] = None
    plan: Optional[ReleasePlan] = None
    audit: list[AuditEvent] = Field(default_factory=list)
    approval: Optional[ApprovalRequest] = None
    execution_results: list[ExecutionActionResult] = Field(default_factory=list)
    summary: SessionSummary = Field(default_factory=SessionSummary)
    evidence: dict[str, Any] = Field(default_factory=dict)
