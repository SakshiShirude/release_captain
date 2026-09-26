import httpx
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.models import TestResult as TestOutcome
from app.routes import SESSIONS
from app.services import execution_service, github_service


client = TestClient(app)


def setup_function() -> None:
    SESSIONS.clear()
    get_settings.cache_clear()


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["sandbox_enabled"] is False
    assert response.json()["execution_enabled"] is False
    assert response.json()["local_test_runner_enabled"] is False
    assert response.json()["analysis_only"] is True


def test_demo_flow_waits_for_approval_and_validates_plan() -> None:
    response = client.post("/api/sessions", json={"repository_url": "https://github.com/example/repo", "branch": "main", "test_command": "pytest"})
    assert response.status_code == 201
    session = response.json()
    assert session["status"] == "ready_for_approval"
    assert session["analysis_only"] is True
    assert session["sandbox_enabled"] is False
    assert session["plan"]["bump"] == "minor"
    assert "## Release Summary" in session["plan"]["release_notes"]
    assert "## Features" in session["plan"]["release_notes"]
    assert "Add release capsule summary" in session["plan"]["release_notes"]
    assert "feat: add release capsule summary" not in session["plan"]["release_notes"]
    assert session["test_result"]["status"] == "unavailable"
    bad = client.post(f"/api/sessions/{session['id']}/approve", json={"approved": True, "plan_version": "v9.9.9", "repository_url": session["repository_url"], "actions": session["plan"]["proposed_actions"]})
    assert bad.status_code == 409
    good = client.post(f"/api/sessions/{session['id']}/approve", json={"approved": True, "plan_version": session["plan"]["recommended_version"], "repository_url": session["repository_url"], "actions": session["plan"]["proposed_actions"]})
    assert good.status_code == 200
    approved = good.json()
    assert approved["status"] == "completed"
    assert approved["audit"][-1]["action"] == "execute_release"
    assert approved["audit"][-1]["status"] == "completed"


def test_test_command_is_allowlisted() -> None:
    response = client.post("/api/sessions", json={"repository_url": "https://github.com/example/repo", "test_command": "rm -rf /"})
    assert response.status_code == 201
    assert response.json()["status"] == "failed"


def test_namespaced_canary_tag_is_accepted() -> None:
    response = client.post("/api/sessions", json={"repository_url": "https://github.com/paperclipai/paperclip", "branch": "master", "previous_tag": "canary/v2026.926.0-canary.2", "test_command": "pytest"})
    assert response.status_code == 201
    assert response.json()["status"] == "ready_for_approval"
    assert response.json()["plan"]["recommended_version"] == "v2026.927.0"
    assert response.json()["test_result"]["status"] == "unavailable"


def test_real_mode_collects_github_evidence_and_surfaces_risks(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "false")
    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        query = dict(request.url.params)
        if path == "/repos/acme/widgets":
            return httpx.Response(200, json={"default_branch": "main"})
        if path == "/repos/acme/widgets/tags":
            return httpx.Response(200, json=[{"name": "v1.2.3"}])
        if path == "/repos/acme/widgets/branches/main":
            return httpx.Response(200, json={"commit": {"sha": "head123"}})
        if path == "/repos/acme/widgets/compare/v1.2.3...main":
            return httpx.Response(
                200,
                json={
                    "html_url": "https://github.com/acme/widgets/compare/v1.2.3...main",
                    "commits": [
                        {
                            "sha": "a1",
                            "commit": {"message": "feat: ship search mode", "author": {"name": "Alice"}},
                            "author": {"login": "alice"},
                        },
                        {
                            "sha": "b2",
                            "commit": {"message": "fix: handle retries", "author": {"name": "Bob"}},
                            "author": {"login": "bob"},
                        },
                    ],
                    "files": [
                        {"filename": "app/api.py", "status": "modified", "additions": 10, "deletions": 2, "changes": 12},
                        {"filename": "app/legacy.py", "status": "removed", "additions": 0, "deletions": 40, "changes": 40},
                    ],
                },
            )
        if path == "/repos/acme/widgets/commits/a1/pulls":
            return httpx.Response(
                200,
                json=[
                    {
                        "number": 10,
                        "title": "Ship search mode",
                        "merged_at": "2026-09-26T00:00:00Z",
                        "labels": [{"name": "enhancement"}],
                        "user": {"login": "alice"},
                    }
                ],
            )
        if path == "/repos/acme/widgets/commits/b2/pulls":
            return httpx.Response(
                200,
                json=[
                    {
                        "number": 11,
                        "title": "Handle retries",
                        "merged_at": "2026-09-26T00:00:00Z",
                        "labels": [{"name": "bug"}],
                        "user": {"login": "bob"},
                    }
                ],
            )
        if path == "/repos/acme/widgets/actions/runs" and query.get("branch") == "main":
            return httpx.Response(
                200,
                json={
                    "workflow_runs": [
                        {
                            "name": "CI",
                            "status": "completed",
                            "conclusion": "failure",
                            "html_url": "https://github.com/acme/widgets/actions/runs/1",
                            "head_sha": "head123",
                        }
                    ]
                },
            )
        raise AssertionError(f"Unexpected GitHub request: {request.method} {request.url}")

    def build_client(timeout_seconds: float, token: str | None) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url="https://api.github.com", transport=httpx.MockTransport(handler))

    monkeypatch.setattr(github_service, "_build_client", build_client)

    response = client.post(
        "/api/sessions",
        json={"repository_url": "https://github.com/acme/widgets", "branch": "main", "test_command": "pytest"},
    )
    assert response.status_code == 201
    session = response.json()
    assert session["status"] == "ready_for_approval"
    assert session["plan"]["current_version"] == "v1.2.3"
    assert session["plan"]["recommended_version"] == "v1.3.0"
    assert session["plan"]["bump"] == "minor"
    assert session["test_result"]["status"] == "unavailable"
    assert session["evidence"]["source"] == "github"
    assert session["evidence"]["base_ref"] == "v1.2.3"
    assert len(session["pull_requests"]) == 2
    assert session["evidence"]["changed_files"][1]["status"] == "removed"
    assert "## Release Summary" in session["plan"]["release_notes"]
    assert "## Features" in session["plan"]["release_notes"]
    assert "## Fixes" in session["plan"]["release_notes"]
    assert "## Risks to Review" in session["plan"]["release_notes"]
    assert "Ship search mode" in session["plan"]["release_notes"]
    risk_titles = {risk["title"] for risk in session["plan"]["risks"]}
    assert "Removed files may indicate a breaking surface change" in risk_titles
    assert "Recent CI runs are failing" in risk_titles

    evidence = client.get(f"/api/sessions/{session['id']}/evidence")
    assert evidence.status_code == 200
    payload = evidence.json()
    assert payload["evidence"]["ci_runs"][0]["conclusion"] == "failure"
    assert payload["commits"][0]["category"] == "features"


def test_real_mode_approval_stays_blocked_without_execution_runner(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "false")
    get_settings.cache_clear()

    async def fake_collect(*args, **kwargs):
        return (
            [github_service.categorize("fix: patch parser", "abc123", "release-bot")],
            [],
            {
                "source": "github",
                "current_version": "v2.0.0",
                "changed_files": [],
                "ci_runs": [],
                "base_ref": "v2.0.0",
            },
        )

    monkeypatch.setattr("app.routes.collect", fake_collect)

    response = client.post(
        "/api/sessions",
        json={"repository_url": "https://github.com/acme/widgets", "branch": "main", "test_command": "pytest"},
    )
    assert response.status_code == 201
    session = response.json()
    assert session["status"] == "ready_for_approval"

    approve_response = client.post(
        f"/api/sessions/{session['id']}/approve",
        json={
            "approved": True,
            "plan_version": session["plan"]["recommended_version"],
            "repository_url": session["repository_url"],
            "actions": session["plan"]["proposed_actions"],
        },
    )
    assert approve_response.status_code == 200
    approved = approve_response.json()
    assert approved["status"] == "approved"
    assert approved["audit"][-1]["action"] == "execute_release"
    assert approved["audit"][-1]["status"] == "blocked"


def test_real_mode_execution_can_complete_with_github_executor(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("RELEASE_CAPTAIN_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    get_settings.cache_clear()

    async def fake_collect(*args, **kwargs):
        return (
            [github_service.categorize("fix: patch parser", "abc123", "release-bot")],
            [],
            {
                "source": "github",
                "current_version": "v2.0.0",
                "changed_files": [],
                "ci_runs": [],
                "base_ref": "v2.0.0",
                "head_sha": "abc123",
            },
        )

    async def fake_create_release_artifacts(*args, **kwargs):
        return [
            {"action": "Create tag v2.0.1", "status": "completed", "detail": "Created refs/tags/v2.0.1"},
            {"action": "Create GitHub release v2.0.1", "status": "completed", "detail": "https://github.com/acme/widgets/releases/tag/v2.0.1"},
        ]

    monkeypatch.setattr("app.routes.collect", fake_collect)
    monkeypatch.setattr("app.services.release_service.create_release_artifacts", fake_create_release_artifacts)

    response = client.post(
        "/api/sessions",
        json={"repository_url": "https://github.com/acme/widgets", "branch": "main", "test_command": "pytest"},
    )
    assert response.status_code == 201
    session = response.json()
    assert session["plan"]["proposed_actions"] == ["Create tag v2.0.1", "Create GitHub release v2.0.1"]

    approve_response = client.post(
        f"/api/sessions/{session['id']}/approve",
        json={
            "approved": True,
            "plan_version": session["plan"]["recommended_version"],
            "repository_url": session["repository_url"],
            "actions": session["plan"]["proposed_actions"],
        },
    )
    assert approve_response.status_code == 200
    approved = approve_response.json()
    assert approved["status"] == "completed"
    assert approved["audit"][-1]["action"] == "execute_release"
    assert approved["audit"][-1]["status"] == "completed"


def test_local_test_runner_fallback_can_be_used_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("RELEASE_CAPTAIN_SANDBOX_ENABLED", "true")
    monkeypatch.setenv("RELEASE_CAPTAIN_LOCAL_TEST_RUNNER_ENABLED", "true")
    get_settings.cache_clear()

    async def fake_collect(*args, **kwargs):
        return (
            [github_service.categorize("fix: patch parser", "abc123", "release-bot")],
            [],
            {
                "source": "github",
                "current_version": "v2.0.0",
                "changed_files": [],
                "ci_runs": [],
                "base_ref": "v2.0.0",
            },
        )

    def fake_run_local(command: str, repository_url: str, branch: str, timeout_seconds: float) -> TestOutcome:
        return TestOutcome(
            command=command,
            status="passed",
            exit_code=0,
            duration_seconds=1.2,
            passed_count=24,
            failed_count=0,
            log_excerpt="24 passed in 1.20s",
            sandbox_provider="local-temp-runner",
        )

    monkeypatch.setattr("app.routes.collect", fake_collect)
    monkeypatch.setattr(execution_service, "_run_local", fake_run_local)

    response = client.post(
        "/api/sessions",
        json={"repository_url": "https://github.com/acme/widgets", "branch": "main", "test_command": "pytest"},
    )
    assert response.status_code == 201
    session = response.json()
    assert session["status"] == "ready_for_approval"
    assert session["test_result"]["status"] == "passed"
    assert session["test_result"]["sandbox_provider"] == "local-temp-runner"
