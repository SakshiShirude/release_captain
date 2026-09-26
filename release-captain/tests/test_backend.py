from fastapi.testclient import TestClient

from app.main import app
from app.routes import SESSIONS


client = TestClient(app)


def setup_function() -> None:
    SESSIONS.clear()


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_demo_flow_waits_for_approval_and_validates_plan() -> None:
    response = client.post("/api/sessions", json={"repository_url": "https://github.com/example/repo", "branch": "main", "test_command": "pytest"})
    assert response.status_code == 201
    session = response.json()
    assert session["status"] == "ready_for_approval"
    assert session["plan"]["bump"] == "minor"
    bad = client.post(f"/api/sessions/{session['id']}/approve", json={"approved": True, "plan_version": "v9.9.9", "repository_url": session["repository_url"], "actions": session["plan"]["proposed_actions"]})
    assert bad.status_code == 409
    good = client.post(f"/api/sessions/{session['id']}/approve", json={"approved": True, "plan_version": session["plan"]["recommended_version"], "repository_url": session["repository_url"], "actions": session["plan"]["proposed_actions"]})
    assert good.status_code == 200
    assert good.json()["status"] == "approved"


def test_test_command_is_allowlisted() -> None:
    response = client.post("/api/sessions", json={"repository_url": "https://github.com/example/repo", "test_command": "rm -rf /"})
    assert response.status_code == 201
    assert response.json()["status"] == "failed"


def test_namespaced_canary_tag_is_accepted() -> None:
    response = client.post("/api/sessions", json={"repository_url": "https://github.com/paperclipai/paperclip", "branch": "master", "previous_tag": "canary/v2026.926.0-canary.2", "test_command": "pytest"})
    assert response.status_code == 201
    assert response.json()["status"] == "ready_for_approval"
    assert response.json()["plan"]["recommended_version"] == "v2026.927.0"
