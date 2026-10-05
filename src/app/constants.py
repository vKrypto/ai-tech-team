"""Names shared by every component: Redis streams/keys and Mongo collections."""

# Redis Streams (the broker). Each has one consumer group, named after the consuming component.
STREAM_TASKS = "ait:tasks"                  # schedulers -> orchestrator      (new | followup | retry)
STREAM_WORKFLOWS = "ait:workflows"          # orchestrator/api -> engine      (start | resume | rerun)
STREAM_AGENT_JOBS = "ait:agent-jobs"        # engine -> agents                (one agent step)
STREAM_ENGINE_EVENTS = "ait:engine-events"  # engine -> orchestrator monitor  (run outcome)
STREAM_NOTIFICATIONS = "ait:notifications"  # anyone -> notifier

GROUP_ORCHESTRATOR = "orchestrator"
GROUP_ORCHESTRATOR_MONITOR = "orchestrator-monitor"
GROUP_ENGINE = "engine"
GROUP_AGENTS = "agents"
GROUP_NOTIFIER = "notifier"

# Redis keys
KEY_EVENT_SEQ = "ait:seq:events"
KEY_METRICS = "ait:metrics"
KEY_SERVICE = "ait:svc:{kind}:{host}"       # heartbeat, expires
KEY_CANCEL = "ait:cancel:{task_id}"
KEY_JOB_DISPATCHED = "ait:job:{job_id}:dispatched"
KEY_JOB_RESULT = "ait:job:{job_id}:result"
KEY_JOB_DONE = "ait:job:{job_id}:done"      # list, BLPOP'd by the engine
KEY_JOB_HEARTBEAT = "ait:job:{job_id}:hb"
KEY_DELIVERIES = "ait:deliveries:{stream}:{msg_id}"
JOB_TTL = 7 * 24 * 3600

# Mongo collections
C_TASKS = "tasks"
C_MESSAGES = "messages"
C_EVENTS = "events"
C_RUNS = "runs"
C_ARTIFACTS = "artifacts"
C_NOTIFICATIONS = "notifications"
C_SCHEDULES = "schedules"
C_CALENDAR = "calendar_events"
C_GITHUB = "github_prs"
C_MEMORIES = "memories"
C_COUNTERS = "counters"

SERVICE_KINDS = ("scheduler", "orchestrator", "engine", "agent", "notifier")
HEALTH_FILE = "/tmp/ait-healthy"
