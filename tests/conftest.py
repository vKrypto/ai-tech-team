"""In-process test harness: mongomock + fakeredis + in-memory checkpointer + mock provider.
Agent jobs run inline (no broker round-trip), so whole workflows run inside a test."""
import os

os.environ["AI_TEAM_PROVIDERS"] = "mock"
os.environ.setdefault("AI_TEAM_DATA_DIR", "/tmp/ai-team-tests")

import fakeredis  # noqa: E402
import mongomock  # noqa: E402
import pytest  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402


@pytest.fixture
def platform(monkeypatch):
    from app.persistence import checkpoints, store
    from app.runtime import executor
    from app.workflows import registry
    from app.workflows.common import context

    store.use(db=mongomock.MongoClient(tz_aware=True)["test"], redis=fakeredis.FakeRedis(decode_responses=True))
    checkpoints.use(InMemorySaver())
    registry.compiled.cache_clear()
    monkeypatch.setattr(context, "dispatch_and_wait", lambda job: executor.execute(job))
    yield
    registry.compiled.cache_clear()


@pytest.fixture
def make_task(platform, tmp_path, monkeypatch):
    """Create a task already routed to `workflow` and queued, like the orchestrator leaves it. Runs against a
    temporary workspace; the project folder exists unless exists=False."""
    from app.domain.enums import TaskStatus
    from app.persistence import task_repository as tasks
    from app.settings import settings
    monkeypatch.setattr(settings, "workspace_root", tmp_path)

    def make(text: str, workflow: str, project: str = "general", exists: bool = True):
        if project != "general" and exists:
            (tmp_path / project).mkdir(exist_ok=True)
        t = tasks.create(text, "api")
        meta = {"title": text[:40], "project": project, "workflow": workflow, "task_type": "development",
                "model_tier": "fast", "project_is_new": False}
        tasks.set_status(t["id"], TaskStatus.QUEUED, metadata=meta, workflow=workflow, project=project,
                         task_type="development", title=text[:40])
        return t["id"]
    return make
