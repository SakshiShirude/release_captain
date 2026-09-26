from __future__ import annotations

import re

from app.models import CommitChange, ReleasePlan, Risk


PREFIXES = {"feat": "features", "fix": "fixes", "docs": "documentation", "refactor": "refactors", "chore": "chores"}
SECTION_TITLES = {
    "features": "Features",
    "fixes": "Fixes",
    "documentation": "Documentation",
    "refactors": "Refactors",
    "chores": "Chores",
}
CI_FAILURES = {"failure", "timed_out", "cancelled", "startup_failure", "action_required"}


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


def _clean_release_note(message: str) -> str:
    match = re.match(r"^(?P<type>[a-z]+)(?P<bang>!)?(?:\([^)]*\))?:\s*(?P<body>.+)$", message, flags=re.DOTALL)
    body = match.group("body") if match else message
    line = body.strip().splitlines()[0].strip()
    if not line:
        return "Repository change"
    return line[:1].upper() + line[1:]


def _build_release_notes(
    *,
    current_version: str,
    recommended_version: str,
    bump: str,
    categories: dict[str, list[str]],
    risks: list[Risk],
) -> str:
    sections: list[str] = [
        "## Release Summary",
        f"- Baseline version: {current_version}",
        f"- Recommended version: {recommended_version}",
        f"- Release type: {bump}",
    ]

    ordered_categories = ["features", "fixes", "documentation", "refactors", "chores"]
    for category in ordered_categories:
        messages = categories.get(category, [])
        if not messages:
            continue
        section_lines = [f"## {SECTION_TITLES[category]}"]
        section_lines.extend(f"- {_clean_release_note(message)}" for message in messages)
        sections.append("\n".join(section_lines))

    if risks:
        risk_lines = ["## Risks to Review"]
        for risk in risks:
            if risk.evidence:
                evidence_text = "; ".join(risk.evidence[:3])
                risk_lines.append(f"- {risk.title}: {evidence_text}")
            else:
                risk_lines.append(f"- {risk.title}")
        sections.append("\n".join(risk_lines))

    if len(sections) == 1:
        sections.append("## Notes\n- No user-facing changes detected.")

    return "\n\n".join(sections)


def analyze(
    commits: list[CommitChange],
    current_version: str = "0.0.0",
    changed_files: list[dict] | None = None,
    ci_runs: list[dict] | None = None,
) -> ReleasePlan:
    categories: dict[str, list[str]] = {}
    breaking: list[str] = []
    risks: list[Risk] = []
    for commit in commits:
        categories.setdefault(commit.category, []).append(commit.message)
        if commit.breaking:
            breaking.append(commit.message)

    removed_files = [item["path"] for item in changed_files or [] if item.get("status") == "removed"]
    if removed_files:
        risks.append(
            Risk(
                title="Removed files may indicate a breaking surface change",
                severity="medium",
                evidence=removed_files[:10],
            )
        )

    failed_ci = [
        f"{item.get('name', 'workflow')} ({item.get('conclusion') or item.get('status')})"
        for item in ci_runs or []
        if (item.get("conclusion") or item.get("status")) in CI_FAILURES
    ]
    if failed_ci:
        risks.append(
            Risk(
                title="Recent CI runs are failing",
                severity="high",
                evidence=failed_ci[:10],
            )
        )

    bump = "major" if breaking else "minor" if categories.get("features") else "patch"
    if breaking:
        risks.insert(0, Risk(title="Possible breaking change", severity="high", evidence=breaking))
    version = _next_version(current_version, bump)
    notes = _build_release_notes(
        current_version=current_version,
        recommended_version=version,
        bump=bump,
        categories=categories,
        risks=risks,
    )
    return ReleasePlan(
        current_version=current_version,
        recommended_version=version,
        bump=bump,
        summary=f"Recommend a {bump} release based on {len(commits)} commit(s).",
        categories=categories,
        breaking_changes=breaking,
        risks=risks,
        release_notes=notes,
        proposed_actions=[f"Create tag {version}", "Publish release artifacts", "Trigger deployment"],
    )


def categorize(message: str, sha: str = "demo", author: str = "demo") -> CommitChange:
    match = re.match(r"^(?P<type>[a-z]+)(?P<bang>!)?(?:\([^)]*\))?:\s*(?P<body>.+)$", message)
    prefix = match.group("type") if match else "chore"
    category = PREFIXES.get(prefix, "chores")
    breaking = bool(match and match.group("bang")) or "BREAKING CHANGE" in message
    return CommitChange(sha=sha, message=message, author=author, category=category, breaking=breaking)
