"""Small offline entry point for exercising the agent contract.

TrueForge remains the runtime for production sessions. This module only provides
the deterministic demo behavior required for local development and tests.
"""

from __future__ import annotations

import os

from app.services.analysis_service import analyze
from app.services.github_service import collect
from app.services.execution_service import run


async def demo_release_plan(repository_url: str, branch: str = "main", previous_tag: str | None = None) -> dict:
    """Return an offline plan without making external or destructive calls."""
    commits, pull_requests = await collect(repository_url, branch, previous_tag)
    plan = analyze(commits, previous_tag or "0.0.0")
    tests = await run("pytest", demo_mode=True)
    return {
        "repository_url": repository_url,
        "branch": branch,
        "commits": commits,
        "pull_requests": pull_requests,
        "plan": plan,
        "test_result": tests,
        "approval_required": True,
        "demo_mode": os.getenv("DEMO_MODE", "true").lower() == "true",
    }
