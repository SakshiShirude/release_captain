from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import tempfile
import time

from app.models import TestResult

ALLOWED_COMMANDS = {"pytest", "python -m pytest", "npm test", "yarn test", "pnpm test"}


def unavailable_result(command: str, reason: str) -> TestResult:
    return TestResult(
        command=command,
        status="unavailable",
        exit_code=0,
        duration_seconds=0.0,
        passed_count=None,
        failed_count=None,
        log_excerpt=reason,
        sandbox_provider="disabled",
    )


def _public_clone_url(repository_url: str) -> str:
    if re.match(r"^https://github\.com/[^/]+/[^/]+/?$", repository_url):
        return repository_url
    if re.match(r"^https://www\.github\.com/[^/]+/[^/]+/?$", repository_url):
        return repository_url.replace("www.github.com", "github.com")
    raise RuntimeError("Local test runner currently supports public github.com repositories only")


def _best_effort_bootstrap(command: str, repo_dir: str, timeout_seconds: float) -> None:
    if command in {"pytest", "python -m pytest"} and os.path.exists(os.path.join(repo_dir, "requirements.txt")):
        subprocess.run(
            ["python3", "-m", "pip", "install", "-r", "requirements.txt"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )


def _run_local(command: str, repository_url: str, branch: str, timeout_seconds: float) -> TestResult:
    started = time.monotonic()
    temp_dir = tempfile.mkdtemp(prefix="release-captain-")
    repo_dir = os.path.join(temp_dir, "repo")
    try:
        clone = subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", branch, _public_clone_url(repository_url), repo_dir],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if clone.returncode != 0:
            detail = clone.stderr.strip() or clone.stdout.strip() or "git clone failed"
            return TestResult(
                command=command,
                status="failed",
                exit_code=clone.returncode,
                duration_seconds=round(time.monotonic() - started, 3),
                passed_count=None,
                failed_count=None,
                log_excerpt=detail[:500],
                sandbox_provider="local-temp-runner",
            )

        bootstrap_timeout = max(15.0, min(timeout_seconds / 2, 120.0))
        _best_effort_bootstrap(command, repo_dir, bootstrap_timeout)
        proc = subprocess.run(
            command.split(),
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        combined = "\n".join(part for part in [proc.stdout.strip(), proc.stderr.strip()] if part).strip()
        status = "passed" if proc.returncode == 0 else "failed"
        return TestResult(
            command=command,
            status=status,
            exit_code=proc.returncode,
            duration_seconds=round(time.monotonic() - started, 3),
            passed_count=None,
            failed_count=None,
            log_excerpt=(combined or f"{command} exited with code {proc.returncode}")[:1000],
            sandbox_provider="local-temp-runner",
        )
    except subprocess.TimeoutExpired:
        return TestResult(
            command=command,
            status="failed",
            exit_code=124,
            duration_seconds=round(time.monotonic() - started, 3),
            passed_count=None,
            failed_count=None,
            log_excerpt=f"Timed out after {int(timeout_seconds)} seconds",
            sandbox_provider="local-temp-runner",
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def run(
    command: str,
    demo_mode: bool = True,
    sandbox_enabled: bool = True,
    *,
    repository_url: str | None = None,
    branch: str = "main",
    timeout_seconds: float = 120.0,
    local_test_runner_enabled: bool = False,
) -> TestResult:
    if command not in ALLOWED_COMMANDS:
        raise ValueError(f"Unsupported test command. Choose one of: {', '.join(sorted(ALLOWED_COMMANDS))}")
    if not sandbox_enabled:
        await asyncio.sleep(0)
        return unavailable_result(command, "Sandbox execution disabled; analysis-only mode active")
    started = time.monotonic()
    if demo_mode:
        await asyncio.sleep(0)
        return TestResult(command=command, status="passed", exit_code=0, duration_seconds=round(time.monotonic() - started, 3), passed_count=12, failed_count=0, log_excerpt="12 passed in 0.42s", sandbox_provider="demo-sandbox")
    if local_test_runner_enabled and repository_url:
        return await asyncio.to_thread(_run_local, command, repository_url, branch, timeout_seconds)
    raise RuntimeError("Real sandbox execution is not configured yet; enable RELEASE_CAPTAIN_LOCAL_TEST_RUNNER_ENABLED for the local runner fallback")
