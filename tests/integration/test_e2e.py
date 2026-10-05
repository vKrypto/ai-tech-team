"""End-to-end scenarios against a running platform on the mock provider (AI_TEAM_PROVIDERS=["mock"]).

    AI_TEAM_E2E_URL=http://localhost:8765 pytest tests/integration -v

Skipped unless AI_TEAM_E2E_URL is set. Uses the mock provider's markers: [ask] [fail] [slow] [code].
"""
import json
import os
import time
import urllib.error
import urllib.request

import pytest

BASE = os.environ.get("AI_TEAM_E2E_URL", "")
pytestmark = pytest.mark.skipif(not BASE, reason="set AI_TEAM_E2E_URL to a running stack (mock provider)")
FINAL = {"done", "failed", "cancelled", "hold:human_required"}


def call(method: str, path: str, body=None):
    req = urllib.request.Request(BASE.rstrip("/") + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or "null")
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "detail": e.read().decode()}


def wait(tid: int, until=FINAL, timeout: float = 120) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        t = call("GET", f"/api/tasks/{tid}")
        if t["status"] in until:
            return t
        time.sleep(0.5)
    raise AssertionError(f"task {tid} stuck in {t['status']}: {t.get('error')}")


def new(text: str, project: str | None = None) -> int:
    return call("POST", "/api/tasks", {"text": text, "project": project})["id"]


def project() -> str:
    projects = call("GET", "/api/meta")["projects"]
    assert projects, "workspace has no projects"
    return projects[0]


def test_all_services_alive():
    kinds = [s["kind"] for s in call("GET", "/api/meta")["services"]]
    for k in ("scheduler", "orchestrator", "engine", "agent", "notifier"):
        assert k in kinds


def test_coding_workflow():
    t = wait(new(f"fix the crash in {project()} when the input is empty"))
    assert t["status"] == "done" and t["workflow"] == "coding", t.get("error")
    run = call("GET", f"/api/runs/{t['run_id']}")
    for n in ("inspect_repo", "plan_changes", "implement", "test", "review", "finalize"):
        assert run["nodes"][n]["status"] == "done", n


def test_research_workflow_and_rerun():
    tid = new("research and compare message brokers for small teams")
    t = wait(tid)
    assert t["status"] == "done" and t["workflow"] == "research"
    r = call("POST", f"/api/runs/{t['run_id']}/nodes/analyze/rerun")
    assert r.get("status") == "queued", r
    time.sleep(0.5)
    t = wait(tid, {"done", "failed"})
    nodes = call("GET", f"/api/runs/{t['run_id']}")["nodes"]
    assert t["status"] == "done"
    assert nodes["analyze"]["attempts"] == 2 and nodes["synthesize"]["attempts"] == 2
    assert nodes["plan"]["attempts"] == 1   # nodes before the re-run point are not repeated


def test_task_execution_with_coding_subgraph():
    t = wait(new("what is the best way to structure tests? [code]"))
    assert t["status"] == "done" and t["workflow"] == "task_execution"
    nodes = call("GET", f"/api/runs/{t['run_id']}")["nodes"]
    assert nodes["implement"]["status"] == "done" and nodes["complete"]["status"] == "done"


def test_human_hold_and_answer():
    tid = new(f"implement a cache layer in {project()} [ask]")
    t = wait(tid)
    assert t["status"] == "hold:human_required" and t["hold"]["options"]
    assert call("POST", f"/api/tasks/{tid}/answer", {"option": "A", "text": "keep it small"})["status"] == "queued"
    assert wait(tid)["status"] == "done"


def test_failure_hold_then_abort():
    tid = new(f"implement retries in {project()} [fail]")
    t = wait(tid)
    assert t["status"] == "hold:human_required" and t["hold"]["kind"] == "error"
    call("POST", f"/api/tasks/{tid}/answer", {"option": "abort"})
    assert wait(tid)["status"] == "failed"


def test_follow_up_conversation():
    tid = new(f"fix the crash in {project()} when the input is empty")
    assert wait(tid)["status"] == "done"
    r = call("POST", f"/api/tasks/{tid}/messages", {"text": "also explain the root cause"})
    assert r.get("turn") == 2, r
    t = wait(tid, {"done", "failed"})
    assert t["status"] == "done" and t["run_id"].endswith("-t2-a1")
    roles = [m["role"] for m in call("GET", f"/api/tasks/{tid}/messages")]
    assert roles == ["user", "assistant", "user", "assistant"]


def test_cancel():
    tid = new("research something slow [slow]")
    wait(tid, {"processing"})
    assert call("POST", f"/api/tasks/{tid}/cancel")["status"] == "cancelled"
    time.sleep(3)
    assert call("GET", f"/api/tasks/{tid}")["status"] == "cancelled"


def test_notifications():
    time.sleep(1)
    n = call("GET", "/api/notifications")
    assert n["items"], "no notifications recorded"
