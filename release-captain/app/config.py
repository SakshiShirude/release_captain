from __future__ import annotations

from functools import lru_cache
import os
from typing import Optional

from pydantic import BaseModel, Field


class Settings(BaseModel):
    demo_mode: bool = Field(default=True)
    github_token: Optional[str] = None
    request_timeout_seconds: float = 20.0
    test_timeout_seconds: float = 120.0


@lru_cache
def get_settings() -> Settings:
    raw_demo = os.getenv("DEMO_MODE", "true").lower()
    return Settings(
        demo_mode=raw_demo in {"1", "true", "yes", "on"},
        github_token=os.getenv("GITHUB_TOKEN"),
    )
