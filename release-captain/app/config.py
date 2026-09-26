from __future__ import annotations

from functools import lru_cache
import os
from typing import Optional

from pydantic import BaseModel, Field


def _env_flag(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


class Settings(BaseModel):
    demo_mode: bool = Field(default=True)
    sandbox_enabled: bool = Field(default=False)
    execution_enabled: bool = Field(default=False)
    local_test_runner_enabled: bool = Field(default=False)
    github_token: Optional[str] = None
    request_timeout_seconds: float = 20.0
    test_timeout_seconds: float = 120.0


@lru_cache
def get_settings() -> Settings:
    return Settings(
        demo_mode=_env_flag("DEMO_MODE", True),
        sandbox_enabled=_env_flag("RELEASE_CAPTAIN_SANDBOX_ENABLED", _env_flag("TRUEFORGE_SANDBOX_ENABLED", False)),
        execution_enabled=_env_flag("RELEASE_CAPTAIN_EXECUTION_ENABLED", False),
        local_test_runner_enabled=_env_flag("RELEASE_CAPTAIN_LOCAL_TEST_RUNNER_ENABLED", False),
        github_token=os.getenv("GITHUB_TOKEN"),
    )
