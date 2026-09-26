import re

from app.models import CommitChange, ReleasePlan, Risk


PREFIXES = {"feat": "features", "fix": "fixes", "docs": "documentation", "refactor": "refactors", "chore": "chores"}


def _next_version(current: str, bump: str) -> str:
    # Accept ordinary tags (v1.2.3) and namespaced/prerelease tags such as
    # canary/v2026.926.0-canary.2 by using their first three numeric parts.
    numbers = re.findall(r"\d+", current)
    parts = [int(p) for p in numbers[:3]]
    while len(parts) < 3:
        parts.append(0)
    index = {"major": 0, "minor": 1, "patch": 2}[bump]
    parts[index] += 1
    for i in range(index + 1, 3):
        parts[i] = 0
    return "v" + ".".join(map(str, parts))


def analyze(commits: list[CommitChange], current_version: str = "0.0.0") -> ReleasePlan:
    categories: dict[str, list[str]] = {}
    breaking: list[str] = []
    for commit in commits:
        categories.setdefault(commit.category, []).append(commit.message)
        if commit.breaking:
            breaking.append(commit.message)
    bump = "major" if breaking else "minor" if categories.get("features") else "patch"
    risks = [Risk(title="Possible breaking change", severity="high", evidence=breaking)] if breaking else []
    version = _next_version(current_version, bump)
    notes = "\n".join(f"- {message}" for messages in categories.values() for message in messages)
    return ReleasePlan(
        current_version=current_version,
        recommended_version=version,
        bump=bump,
        summary=f"Recommend a {bump} release based on {len(commits)} commit(s).",
        categories=categories,
        breaking_changes=breaking,
        risks=risks,
        release_notes=notes or "No user-facing changes detected.",
        proposed_actions=[f"Create tag {version}", "Publish release artifacts", "Trigger deployment"],
    )


def categorize(message: str, sha: str = "demo", author: str = "demo") -> CommitChange:
    match = re.match(r"^(?P<type>[a-z]+)(?P<bang>!)?(?:\([^)]*\))?:\s*(?P<body>.+)$", message)
    prefix = match.group("type") if match else "chore"
    category = PREFIXES.get(prefix, "chores")
    breaking = bool(match and match.group("bang")) or "BREAKING CHANGE" in message
    return CommitChange(sha=sha, message=message, author=author, category=category, breaking=breaking)
