from __future__ import annotations

import asyncio
import base64
import json
import time
from contextvars import ContextVar
from typing import Any, Optional, Tuple
from urllib.parse import quote, urlparse
from uuid import uuid4

import httpx

from app.models import CommitChange, ObservedToolCall, PullRequestChange, RepositoryMetadata
from app.services.analysis_service import categorize


DEMO_MESSAGES = [
    "feat: add release capsule summary",
    "fix: make approval validation strict",
    "docs: document demo mode",
]

_active_observed_calls: ContextVar[Optional[list[dict[str, Any]]]] = ContextVar(
    "active_observed_calls", default=None
)


class GitHubCollectionError(RuntimeError):
    def __init__(self, detail: str, observed_calls: list[dict[str, Any]]) -> None:
        super().__init__(detail)
        self.observed_calls = observed_calls


def _parse_repository(repository_url: str) -> tuple[str, str]:
    parsed = urlparse(repository_url)
    if parsed.netloc not in {"github.com", "www.github.com"}:
        raise ValueError("Only github.com repositories are supported")
    path = parsed.path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2:
        raise ValueError("Repository URL must look like https://github.com/owner/repo")
    return parts[0], parts[1]


def _headers(token: Optional[str]) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "release-captain",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


class _ObservedGithubClient(httpx.AsyncClient):
    def __init__(self, *, timeout_seconds: float, token: Optional[str], calls: Optional[list[dict[str, Any]]] = None) -> None:
        headers = _headers(token)
        super().__init__(
            base_url="https://api.github.com",
            headers=headers,
            timeout=timeout_seconds,
            follow_redirects=True,
        )
        self._observed_calls = calls

    async def request(self, method: str, url: Any, **kwargs: Any) -> httpx.Response:
        started = time.monotonic()
        try:
            response = await super().request(method, url, **kwargs)
        except Exception as exc:
            if self._observed_calls is not None:
                full_url = self.base_url.join(url) if isinstance(url, str) and not url.startswith("http") else httpx.URL(url)
                self._observed_calls.append(
                    ObservedToolCall(
                        id=str(uuid4()),
                        tool_name="GitHub REST API",
                        method=method.upper(),
                        path=full_url.path,
                        status="error",
                        duration_seconds=round(time.monotonic() - started, 3),
                        detail=f"Request failed: {str(exc)[:240]}",
                    ).model_dump()
                )
            raise

        if self._observed_calls is not None:
            self._observed_calls.append(
                ObservedToolCall(
                    id=str(uuid4()),
                    tool_name="GitHub REST API",
                    method=method.upper(),
                    path=response.request.url.path,
                    status="success" if response.is_success else "error",
                    status_code=response.status_code,
                    duration_seconds=round(time.monotonic() - started, 3),
                    detail=f"HTTP {response.status_code} {response.reason_phrase}".strip(),
                ).model_dump()
            )
        return response


def _build_client(timeout_seconds: float, token: Optional[str]) -> httpx.AsyncClient:
    return _ObservedGithubClient(
        timeout_seconds=timeout_seconds,
        token=token,
        calls=_active_observed_calls.get(),
    )


async def inspect_repository_metadata(
    repository_url: str,
    *,
    demo_mode: bool = True,
    github_token: Optional[str] = None,
    request_timeout_seconds: float = 20.0,
) -> RepositoryMetadata:
    owner, repo = _parse_repository(repository_url)
    try:
        async with _build_client(request_timeout_seconds, github_token) as client:
            repository, branches, tags, files = await asyncio.gather(
                _get_json(client, f"/repos/{owner}/{repo}"),
                _get_json(client, f"/repos/{owner}/{repo}/branches", params={"per_page": 100}),
                _get_json(client, f"/repos/{owner}/{repo}/tags", params={"per_page": 100}, missing_ok=True),
                asyncio.gather(
                    *[
                        _get_json(client, f"/repos/{owner}/{repo}/contents/{path}", missing_ok=True)
                        for path in (
                            "package.json",
                            "pnpm-lock.yaml",
                            "yarn.lock",
                            "package-lock.json",
                            "pytest.ini",
                            "tox.ini",
                            "pyproject.toml",
                            "setup.cfg",
                            "setup.py",
                        )
                    ]
                ),
            )
    except (RuntimeError, httpx.HTTPError):
        if not demo_mode:
            raise
        return RepositoryMetadata(
            repository_key=f"{owner}/{repo}",
            default_branch="main",
            branches=["main", "release/next"],
            tags=["v1.4.0", "v1.3.0", "v1.2.0"],
            test_command="pytest",
            test_command_reason="Live repository inspection was unavailable, so demo metadata is shown.",
            source="demo",
        )

    default_branch = repository.get("default_branch") or "main"
    branch_names = [item.get("name") for item in branches if item.get("name")]
    if default_branch not in branch_names:
        branch_names.insert(0, default_branch)
    tag_names = [item.get("name") for item in tags or [] if item.get("name")]
    file_text = {
        path: _decode_content(data)
        for path, data in zip(
            (
                "package.json",
                "pnpm-lock.yaml",
                "yarn.lock",
                "package-lock.json",
                "pytest.ini",
                "tox.ini",
                "pyproject.toml",
                "setup.cfg",
                "setup.py",
            ),
            files,
        )
    }
    command, reason = _detect_test_command(file_text)
    return RepositoryMetadata(
        repository_key=f"{owner}/{repo}",
        default_branch=default_branch,
        branches=branch_names,
        tags=tag_names,
        test_command=command,
        test_command_reason=reason,
        source="live",
    )


def _decode_content(payload: Any) -> str:
    if not isinstance(payload, dict) or payload.get("encoding") != "base64":
        return ""
    try:
        return base64.b64decode(payload.get("content", "")).decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        return ""


def _detect_test_command(files: dict[str, str]) -> tuple[str, str]:
    package_text = files.get("package.json", "")
    if package_text:
        try:
            package = json.loads(package_text)
            scripts = package.get("scripts") or {}
            test_script = scripts.get("test", "") if isinstance(scripts, dict) else ""
            has_test = isinstance(test_script, str) and test_script.strip() and test_script.strip() != 'echo "Error: no test specified" && exit 1'
            if has_test:
                package_manager = package.get("packageManager", "")
                if files.get("pnpm-lock.yaml") or str(package_manager).startswith("pnpm@"):
                    return "pnpm test", "Detected a package.json test script and pnpm lockfile."
                if files.get("yarn.lock") or str(package_manager).startswith("yarn@"):
                    return "yarn test", "Detected a package.json test script and yarn lockfile."
                return "npm test", "Detected a package.json test script."
        except (json.JSONDecodeError, TypeError):
            pass

    if files.get("pytest.ini") or files.get("tox.ini"):
        return "pytest", "Detected root pytest configuration."
    if "[tool.pytest.ini_options]" in files.get("pyproject.toml", "") or "pytest" in files.get("pyproject.toml", ""):
        return "pytest", "Detected pytest configuration in pyproject.toml."
    if "[tool:pytest]" in files.get("setup.cfg", "") or "pytest" in files.get("setup.cfg", ""):
        return "pytest", "Detected pytest configuration in setup.cfg."
    if files.get("setup.py"):
        return "pytest", "Detected a Python project layout."
    return "", "No allowlisted test command could be inferred from repository files."


async def _post_json(client: httpx.AsyncClient, path: str, payload: dict[str, Any]) -> Any:
    response = await client.post(path, json=payload)
    if response.status_code == 422:
        return response.json()
    if response.status_code == 403 and response.headers.get("x-ratelimit-remaining") == "0":
        raise RuntimeError("GitHub API rate limit exceeded; set GITHUB_TOKEN to continue")
    response.raise_for_status()
    return response.json()


async def _get_json(
    client: httpx.AsyncClient,
    path: str,
    *,
    params: Optional[dict[str, Any]] = None,
    missing_ok: bool = False,
) -> Any:
    response = await client.get(path, params=params)
    if missing_ok and response.status_code == 404:
        return None
    if response.status_code == 404:
        raise ValueError(f"GitHub resource not found: {path}")
    if response.status_code == 403 and response.headers.get("x-ratelimit-remaining") == "0":
        raise RuntimeError("GitHub API rate limit exceeded; set GITHUB_TOKEN to continue")
    response.raise_for_status()
    return response.json()


def _demo_evidence(branch: str, previous_tag: Optional[str]) -> dict[str, Any]:
    return {
        "source": "demo",
        "default_branch": branch,
        "base_ref": previous_tag or "v1.4.0",
        "baseline_reason": "demo_mode",
        "current_ref": branch,
        "current_version": previous_tag or "v1.4.0",
        "latest_tag": previous_tag or "v1.4.0",
        "compare_url": None,
        "changed_files": [],
        "ci_runs": [],
    }


async def _latest_tag(client: httpx.AsyncClient, owner: str, repo: str) -> Optional[str]:
    data = await _get_json(client, f"/repos/{owner}/{repo}/tags", params={"per_page": 1}, missing_ok=True)
    if not data:
        return None
    return data[0].get("name")


def _select_baseline(branch: str, default_branch: str, previous_tag: Optional[str], latest_tag: Optional[str]) -> tuple[Optional[str], str, str]:
    if previous_tag:
        return previous_tag, previous_tag, "requested_tag"
    if branch != default_branch:
        return default_branch, latest_tag or "0.0.0", "branch_against_default"
    if latest_tag:
        return latest_tag, latest_tag, "latest_tag"
    return None, "0.0.0", "recent_commits"


def _build_commit(item: dict[str, Any]) -> CommitChange:
    message = item.get("commit", {}).get("message", "").strip() or "chore: update repository"
    author = item.get("author", {}).get("login") or item.get("commit", {}).get("author", {}).get("name") or "unknown"
    return categorize(message=message, sha=item.get("sha", "unknown"), author=author)


async def _recent_commits(client: httpx.AsyncClient, owner: str, repo: str, branch: str) -> list[CommitChange]:
    data = await _get_json(client, f"/repos/{owner}/{repo}/commits", params={"sha": branch, "per_page": 20})
    return [_build_commit(item) for item in data]


async def _compare(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    base_ref: str,
    head_ref: str,
    *,
    strict: bool,
) -> Optional[dict[str, Any]]:
    try:
        return await _get_json(
            client,
            f"/repos/{owner}/{repo}/compare/{quote(base_ref, safe='')}...{quote(head_ref, safe='')}",
        )
    except ValueError:
        if strict:
            raise
        return None


async def _pull_requests_for_commits(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    commit_shas: list[str],
) -> list[PullRequestChange]:
    pull_requests: dict[int, PullRequestChange] = {}
    for sha in commit_shas[:25]:
        data = await _get_json(client, f"/repos/{owner}/{repo}/commits/{sha}/pulls", params={"per_page": 5}, missing_ok=True)
        for item in data or []:
            if not item.get("merged_at"):
                continue
            number = item["number"]
            if number in pull_requests:
                continue
            labels = [label["name"] for label in item.get("labels", [])]
            author = (item.get("user") or {}).get("login") or "unknown"
            pull_requests[number] = PullRequestChange(
                number=number,
                title=item.get("title") or f"PR #{number}",
                author=author,
                labels=labels,
                merged=True,
            )
    return list(sorted(pull_requests.values(), key=lambda pr: pr.number))


async def _ci_runs(client: httpx.AsyncClient, owner: str, repo: str, branch: str) -> list[dict[str, Any]]:
    data = await _get_json(
        client,
        f"/repos/{owner}/{repo}/actions/runs",
        params={"branch": branch, "per_page": 5},
        missing_ok=True,
    )
    runs = []
    for item in (data or {}).get("workflow_runs", []):
        runs.append(
            {
                "name": item.get("name") or "workflow",
                "status": item.get("status") or "unknown",
                "conclusion": item.get("conclusion"),
                "url": item.get("html_url"),
                "head_sha": item.get("head_sha"),
            }
        )
    return runs


async def collect(
    repository_url: str,
    branch: str,
    previous_tag: Optional[str],
    *,
    demo_mode: bool = True,
    github_token: Optional[str] = None,
    request_timeout_seconds: float = 20.0,
) -> Tuple[list[CommitChange], list[PullRequestChange], dict[str, Any]]:
    # Demo data keeps the backend runnable without GitHub credentials.
    if demo_mode:
        evidence = _demo_evidence(branch, previous_tag)
        owner, repo = _parse_repository(repository_url)
        evidence["observed_tool_calls"] = [
            ObservedToolCall(
                id=f"demo-{index}",
                tool_name="GitHub REST API",
                method="DEMO",
                path=path.format(owner=owner, repo=repo),
                status="simulated",
                detail=detail,
            ).model_dump()
            for index, (path, detail) in enumerate(
                [
                    ("/repos/{owner}/{repo}/commits", "Demo fixture supplied commit evidence; no GitHub request was made."),
                    ("/repos/{owner}/{repo}/pulls", "Demo fixture supplied pull request evidence; no GitHub request was made."),
                    ("/repos/{owner}/{repo}/actions/runs", "Demo fixture supplied CI evidence; no GitHub request was made."),
                ],
                start=1,
            )
        ]
        commits = [categorize(message, f"demo-{i}", "release-captain") for i, message in enumerate(DEMO_MESSAGES, 1)]
        prs = [PullRequestChange(number=101, title="Add release capsule summary", author="release-captain", labels=["enhancement"])]
        return commits, prs, evidence

    owner, repo = _parse_repository(repository_url)
    observed_calls: list[dict[str, Any]] = []
    context_token = _active_observed_calls.set(observed_calls)
    try:
        async with _build_client(request_timeout_seconds, github_token) as client:
            repo_data = await _get_json(client, f"/repos/{owner}/{repo}")
            default_branch = repo_data.get("default_branch") or "main"
            latest_tag = await _latest_tag(client, owner, repo)
            base_ref, current_version, baseline_reason = _select_baseline(branch, default_branch, previous_tag, latest_tag)
            branch_data = await _get_json(client, f"/repos/{owner}/{repo}/branches/{quote(branch, safe='')}")
            head_sha = branch_data.get("commit", {}).get("sha")

            compare_data = None
            if base_ref:
                compare_data = await _compare(
                    client,
                    owner,
                    repo,
                    base_ref,
                    branch,
                    strict=previous_tag is not None,
                )

            if compare_data is not None:
                commits = [_build_commit(item) for item in compare_data.get("commits", [])]
                changed_files = [
                    {
                        "path": item.get("filename"),
                        "status": item.get("status") or "modified",
                        "additions": item.get("additions", 0),
                        "deletions": item.get("deletions", 0),
                        "changes": item.get("changes", 0),
                    }
                    for item in compare_data.get("files", [])
                    if item.get("filename")
                ]
                compare_url = compare_data.get("html_url")
            else:
                commits = await _recent_commits(client, owner, repo, branch)
                changed_files = []
                compare_url = None

            if not commits and head_sha:
                commit_data = await _get_json(client, f"/repos/{owner}/{repo}/commits/{head_sha}")
                commits = [_build_commit(commit_data)]

            pull_requests = await _pull_requests_for_commits(client, owner, repo, [commit.sha for commit in commits])
            ci_runs = await _ci_runs(client, owner, repo, branch)
            evidence = {
                "source": "github",
                "owner": owner,
                "repo": repo,
                "default_branch": default_branch,
                "base_ref": base_ref,
                "baseline_reason": baseline_reason,
                "current_ref": branch,
                "current_version": current_version,
                "latest_tag": latest_tag,
                "head_sha": head_sha,
                "compare_url": compare_url,
                "changed_files": changed_files,
                "ci_runs": ci_runs,
                "observed_tool_calls": observed_calls,
            }
            return commits, pull_requests, evidence
    except Exception as exc:
        raise GitHubCollectionError(str(exc), observed_calls) from exc
    finally:
        _active_observed_calls.reset(context_token)


async def create_release_artifacts(
    repository_url: str,
    *,
    branch: str,
    version: str,
    release_notes: str,
    github_token: str,
    request_timeout_seconds: float = 20.0,
    head_sha: Optional[str] = None,
) -> list[dict[str, str]]:
    owner, repo = _parse_repository(repository_url)
    if not github_token:
        raise RuntimeError("GITHUB_TOKEN is required for release execution")

    async with _build_client(request_timeout_seconds, github_token) as client:
        if not head_sha:
            branch_data = await _get_json(client, f"/repos/{owner}/{repo}/branches/{quote(branch, safe='')}")
            head_sha = branch_data.get("commit", {}).get("sha")
        if not head_sha:
            raise RuntimeError("Could not determine the branch head SHA for release execution")

        actions: list[dict[str, str]] = []
        ref_path = f"/repos/{owner}/{repo}/git/ref/tags/{quote(version, safe='')}"
        existing_ref = await _get_json(client, ref_path, missing_ok=True)
        if existing_ref:
            actions.append({"action": f"Create tag {version}", "status": "skipped", "detail": f"Tag {version} already exists"})
        else:
            tag_result = await _post_json(
                client,
                f"/repos/{owner}/{repo}/git/refs",
                {"ref": f"refs/tags/{version}", "sha": head_sha},
            )
            if isinstance(tag_result, dict) and tag_result.get("ref"):
                actions.append({"action": f"Create tag {version}", "status": "completed", "detail": f"Created {tag_result['ref']}"})
            else:
                raise RuntimeError(f"Failed to create tag {version}")

        existing_release = await _get_json(client, f"/repos/{owner}/{repo}/releases/tags/{version}", missing_ok=True)
        if existing_release:
            actions.append({"action": f"Create GitHub release {version}", "status": "skipped", "detail": f"Release {version} already exists"})
        else:
            release_result = await _post_json(
                client,
                f"/repos/{owner}/{repo}/releases",
                {
                    "tag_name": version,
                    "target_commitish": branch,
                    "name": version,
                    "body": release_notes,
                    "draft": False,
                    "prerelease": False,
                    "generate_release_notes": False,
                },
            )
            if isinstance(release_result, dict) and release_result.get("html_url"):
                actions.append(
                    {
                        "action": f"Create GitHub release {version}",
                        "status": "completed",
                        "detail": release_result["html_url"],
                    }
                )
            else:
                raise RuntimeError(f"Failed to create GitHub release {version}")

        return actions
