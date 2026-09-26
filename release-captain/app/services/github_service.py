from typing import Optional, Tuple

from app.models import CommitChange, PullRequestChange
from app.services.analysis_service import categorize


DEMO_MESSAGES = [
    "feat: add release capsule summary",
    "fix: make approval validation strict",
    "docs: document demo mode",
]


async def collect(repository_url: str, branch: str, previous_tag: Optional[str]) -> Tuple[list[CommitChange], list[PullRequestChange]]:
    # External GitHub reads are intentionally isolated here. Demo data keeps the
    # backend runnable without credentials; production integration can replace this service.
    commits = [categorize(message, f"demo-{i}", "release-captain") for i, message in enumerate(DEMO_MESSAGES, 1)]
    prs = [PullRequestChange(number=101, title="Add release capsule summary", author="release-captain", labels=["enhancement"])]
    return commits, prs
