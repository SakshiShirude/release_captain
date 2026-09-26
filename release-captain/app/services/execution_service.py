from __future__ import annotations

import asyncio
import time

from app.models import TestResult

ALLOWED_COMMANDS = {"pytest", "python -m pytest", "npm test", "yarn test", "pnpm test"}


async def run(command: str, demo_mode: bool = True) -> TestResult:
    if command not in ALLOWED_COMMANDS:
        raise ValueError(f"Unsupported test command. Choose one of: {', '.join(sorted(ALLOWED_COMMANDS))}")
    started = time.monotonic()
    if demo_mode:
        await asyncio.sleep(0)
        return TestResult(command=command, status="passed", exit_code=0, duration_seconds=round(time.monotonic() - started, 3), passed_count=12, failed_count=0, log_excerpt="12 passed in 0.42s", sandbox_provider="demo-sandbox")
    raise RuntimeError("Real sandbox execution is not configured yet")
