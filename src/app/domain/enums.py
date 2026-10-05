from enum import StrEnum


class TaskStatus(StrEnum):
    CREATED = "created"                     # scheduler stored it and pushed it to the broker
    QUEUED = "queued"                       # orchestrator understood it and handed a workflow to the engine
    PROCESSING = "processing"               # engine is running the workflow
    HOLD = "hold:human_required"            # waiting for a human decision (see task.hold)
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


ACTIVE = (TaskStatus.CREATED, TaskStatus.QUEUED, TaskStatus.PROCESSING)
FINISHED = (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED)


class TaskType(StrEnum):
    ENQUIRY = "enquiry"
    RESEARCH = "research"                   # r&d
    DEVELOPMENT = "development"
    BUGFIX = "bugfix"
    REVIEW = "review"
    TESTING = "testing"
    PLANNING = "planning"
    DOCS = "docs"
    OPS = "ops"


class Workflow(StrEnum):
    TASK_EXECUTION = "task_execution"
    RESEARCH = "research"
    CODING = "coding"


class Source(StrEnum):
    DASHBOARD = "dashboard"
    GOOGLE_CALENDAR = "google_calendar"
    CRON = "cron"
    GITHUB = "github"
    API = "api"


class RunStatus(StrEnum):
    RUNNING = "running"
    HOLD = "hold"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"                     # asked a human
    DONE = "done"
    FAILED = "failed"


class Tier(StrEnum):
    FAST = "fast"
    BALANCED = "balanced"
    DEEP = "deep"
