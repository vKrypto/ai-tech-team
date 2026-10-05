"""Agent jobs, both ends.

Engine side: dispatch_and_wait() publishes a job once (idempotent by job id) and blocks until its result
appears, so a node re-executed after an engine crash picks up the result of the job it already started.
Agent side: execute() runs the job with the role's provider chain, heartbeating, and deliver() stores the
result where the engine waits for it.
"""
import logging
import threading
import time

from .. import constants as C
from ..agents import factory
from ..domain.events import AgentJob
from ..domain.task_result import AgentResult
from ..guardrails.output import redact
from ..observability import events, metrics
from ..orchestration.dispatcher import publish
from ..persistence.store import redis
from ..settings import settings
from . import cancellation
from .cancellation import Cancelled

log = logging.getLogger(__name__)


# ---- engine side -------------------------------------------------------------------------------------
def dispatch_and_wait(job: AgentJob) -> AgentResult:
    r = redis()
    if r.set(C.KEY_JOB_DISPATCHED.format(job_id=job.job_id), "1", nx=True, ex=C.JOB_TTL):
        publish(C.STREAM_AGENT_JOBS, job)
    deadline = time.monotonic() + settings.cfg("agents.job_timeout_seconds", 7200)
    result_key, done_key = C.KEY_JOB_RESULT.format(job_id=job.job_id), C.KEY_JOB_DONE.format(job_id=job.job_id)
    while True:
        raw = r.get(result_key)
        if raw:
            return AgentResult.model_validate_json(raw)
        if cancellation.is_cancelled(job.task_id):
            raise Cancelled()
        if time.monotonic() > deadline:
            raise TimeoutError(f"agent job {job.job_id} got no result within the job timeout")
        r.blpop([done_key], timeout=5)


# ---- agent side --------------------------------------------------------------------------------------
def existing_result(job_id: str) -> AgentResult | None:
    raw = redis().get(C.KEY_JOB_RESULT.format(job_id=job_id))
    return AgentResult.model_validate_json(raw) if raw else None


def deliver(result: AgentResult) -> None:
    r = redis()
    r.set(C.KEY_JOB_RESULT.format(job_id=result.job_id), result.model_dump_json(), ex=C.JOB_TTL)
    done = C.KEY_JOB_DONE.format(job_id=result.job_id)
    r.rpush(done, "1")
    r.expire(done, C.JOB_TTL)


def execute(job: AgentJob) -> AgentResult:
    me = settings.host
    source = f"{job.role}@{me}"
    log_ev = lambda kind, msg, data=None: events.emit(job.task_id, source, kind, msg, job.run_id, data)
    if cancellation.is_cancelled(job.task_id):
        return AgentResult(job_id=job.job_id, ok=False, cancelled=True, error="cancelled", agent=me)
    stop = threading.Event()

    def heartbeat():
        while not stop.is_set():
            redis().set(C.KEY_JOB_HEARTBEAT.format(job_id=job.job_id), me, ex=60)
            stop.wait(20)

    threading.Thread(target=heartbeat, daemon=True).start()
    log_ev("status", f"picked up `{job.node}` (job {job.job_id}, tier {job.tier})",
           {"phase": "pickup", "step": job.node, "role": job.role, "worker": me})
    t0 = time.monotonic()
    try:
        run = factory.for_job(job).run(job, log_ev, lambda: cancellation.is_cancelled(job.task_id))
        metrics.incr("agent.jobs.ok")
        log_ev("status", f"finished `{job.node}` in {time.monotonic() - t0:.1f}s via {run.provider}/{run.model}"
                         + (f"; asks a human: {run.needs_human.get('problem')}" if run.needs_human else ""),
               {"phase": "finished", "step": job.node, "role": job.role, "provider": run.provider, "model": run.model,
                "seconds": round(time.monotonic() - t0, 1)})
        return AgentResult(job_id=job.job_id, text=redact(run.text), session=run.session,
                           session_key=run.session_key, provider=run.provider, model=run.model,
                           changed_files=sorted(run.changed), needs_human=run.needs_human, agent=me,
                           cost_usd=run.cost_usd)
    except Cancelled:
        log_ev("status", "cancelled")
        return AgentResult(job_id=job.job_id, ok=False, cancelled=True, error="cancelled", agent=me)
    except Exception as e:
        log.exception("job %s failed", job.job_id)
        metrics.incr("agent.jobs.failed")
        log_ev("error", f"{type(e).__name__}: {e}")
        return AgentResult(job_id=job.job_id, ok=False, error=f"{type(e).__name__}: {e}"[:4000], agent=me)
    finally:
        stop.set()
        redis().delete(C.KEY_JOB_HEARTBEAT.format(job_id=job.job_id))
        metrics.incr("agent.jobs.seconds", time.monotonic() - t0)
