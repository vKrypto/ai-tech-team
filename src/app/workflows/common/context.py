"""Node plumbing: status tracking, routing guards, and calling an agent from a node."""
import functools
import logging
import time

from langgraph.errors import GraphBubbleUp
from langgraph.graph import END

from ...domain.events import AgentJob
from ...guardrails.budget import BudgetExceeded, check as check_budget
from ...observability import events
from ...persistence import artifacts, run_repository as runs, task_repository as tasks
from ...runtime import cancellation
from ...runtime.cancellation import Cancelled
from ...runtime.executor import dispatch_and_wait
from ...runtime.run_context import RunContext
from . import branches

log = logging.getLogger(__name__)
OUTPUT_CHARS = 8000
CONTROL = ["handle_error", "approval", END]


class AgentFailed(Exception):
    pass


def tracked(name: str, fn):
    """Record node status on the run, honour cancellation and approval_before, retry failing agent calls,
    and turn errors into state (-> handle_error) instead of exceptions."""
    @functools.wraps(fn)
    def node(state: dict) -> dict:
        ctx = RunContext.of(state)
        cancellation.check(ctx.task_id)
        pol = ctx.policy
        if name in (pol.get("approval_before") or []) and name not in (state.get("approvals") or []):
            return {"human": {"kind": "approval", "node": name, "problem": f"Approve running step `{name}`?",
                              "options": [{"id": "approve", "label": "Approve", "details": "Run the step"},
                                          {"id": "reject", "label": "Reject", "details": "Stop the task"}]}}
        runs.node_start(ctx.run_id, name)
        events.emit(ctx.task_id, f"engine/{name}", "status", f"▶ step `{name}` started", ctx.run_id)
        t0 = time.monotonic()
        attempts = int(pol.get("node_retries", 1)) + 1
        for attempt in range(attempts):
            try:
                updates = fn({**state, "_attempt": attempt}) or {}
                break
            except GraphBubbleUp:
                raise
            except Cancelled:
                events.emit(ctx.task_id, f"engine/{name}", "status", f"■ step `{name}` cancelled", ctx.run_id)
                raise
            except BudgetExceeded as e:
                runs.node_fail(ctx.run_id, name, str(e))
                events.emit(ctx.task_id, f"engine/{name}", "error", f"✗ step `{name}`: {e}", ctx.run_id)
                return {"failed": True, "error": {"node": name, "message": str(e)}}
            except Exception as e:
                msg = f"{type(e).__name__}: {e}"
                log.warning("node %s attempt %s failed: %s", name, attempt + 1, msg)
                events.emit(ctx.task_id, f"engine/{name}", "error", f"attempt {attempt + 1}/{attempts}: {msg}",
                            ctx.run_id)
                if attempt + 1 >= attempts:
                    runs.node_fail(ctx.run_id, name, msg)
                    events.emit(ctx.task_id, f"engine/{name}", "error",
                                f"✗ step `{name}` failed after {attempts} attempt(s) in {time.monotonic() - t0:.1f}s",
                                ctx.run_id)
                    return {"error": {"node": name, "message": msg[:3000]}}
        took = time.monotonic() - t0
        if updates.get("human"):
            runs.node_wait(ctx.run_id, name, updates["human"].get("problem", ""))
            events.emit(ctx.task_id, f"engine/{name}", "human",
                        f"⏸ step `{name}` needs a human ({took:.1f}s): {updates['human'].get('problem', '')}", ctx.run_id)
        elif updates.get("error") or updates.get("failed"):
            pass  # recorded above / by the node itself
        else:
            out = (updates.get("outputs") or {}).get(name)
            runs.node_done(ctx.run_id, name, out)
            events.emit(ctx.task_id, f"engine/{name}", "status", f"✓ step `{name}` done in {took:.1f}s", ctx.run_id)
        return updates
    return node


def guard(nxt):
    """Conditional-edge router: failure ends the run, errors go to handle_error, questions to approval."""
    def route(state: dict) -> str:
        if state.get("failed"):
            return END
        if state.get("error"):
            return "handle_error"
        if state.get("human"):
            return "approval"
        return nxt(state) if callable(nxt) else nxt
    return route


def _section(title: str, body: str | None) -> str:
    return f"## {title}\n{body.strip()}\n\n" if body and body.strip() else ""


def brief(state: dict, node: str, instruction: str, include: list[str] = ()) -> str:
    outputs = state.get("outputs") or {}
    step = state.get("step")
    text = _section(f"Task (turn {state.get('turn', 1)})", state.get("request"))
    text += _section("Earlier conversation on this task", state.get("history"))
    text += _section("Project", state.get("project_info"))
    if branches.uses_git(state):
        base, sub = branches.for_state(state)
        text += _section("Git branch", (
            f"Task #{state['task_id']} branch: `{base}`"
            + (f"\nThis sub-task's branch: `{sub}` (created from `{base}`, merged back into it when done)" if sub else "")
            + "\nAll changes for this task live on these branches, never on main/master. Roles that only inspect or "
              "test: check out the branch to look at the work."))
    text += _section("What the team learned on this project before", state.get("project_memory"))
    if step:
        n = len(state.get("steps") or [])
        text += _section(f"Current step ({state.get('step_index', 0) + 1}/{n})", step.get("instruction"))
    for k in include:
        if outputs.get(k):
            o = outputs[k]
            text += _section(f"Output of `{k}`", o if len(o) <= OUTPUT_CHARS else o[:OUTPUT_CHARS] + "\n...")
    if state.get("changed_files"):
        text += _section("Files changed so far", "\n".join(f"- {f}" for f in state["changed_files"]))
    text += _section(f"Your job now (`{node}`)", instruction)
    ans = state.get("human_answer")
    if ans and ans.get("node") == node:
        choice = " - ".join(x for x in (ans.get("option"), ans.get("label"), ans.get("text")) if x)
        text += _section("Human decision", f"The human answered your question: {choice}\n"
                                           "Continue your step accordingly.")
    return text


def run_agent(state: dict, node: str, role: str, instruction: str, include: list[str] = (),
              tier: str | None = None) -> dict:
    """Run one agent job for this node and return the state updates."""
    ctx = RunContext.of(state)
    check_budget(state, ctx.policy)
    seq = state.get("seq", 0)
    job = AgentJob(job_id=ctx.job_id(node, seq, state.get("_attempt", 0)), task_id=ctx.task_id,
                   run_id=ctx.run_id, node=node, role=role, brief=brief(state, node, instruction, include),
                   project=state.get("project"), tier=tier or state.get("tier") or "balanced",
                   sessions=state.get("sessions") or {}, request=state.get("request", ""))
    events.emit(ctx.task_id, f"engine/{node}", "status", f"dispatching to {role} (job {job.job_id})", ctx.run_id)
    t0 = time.monotonic()
    result = dispatch_and_wait(job)
    events.emit(ctx.task_id, f"engine/{node}", "status" if result.ok else "error",
                f"job {job.job_id} {'ok' if result.ok else 'failed'} after {time.monotonic() - t0:.1f}s"
                f" — {role} on {result.agent or '?'} via {result.provider or '?'}/{result.model or '?'}"
                + (f", {len(result.changed_files)} file(s) changed" if result.changed_files else "")
                + (f", ~${result.cost_usd:.3f}" if result.cost_usd else ""), ctx.run_id)
    if result.cancelled:
        raise Cancelled()
    if not result.ok:
        raise AgentFailed(result.error or "agent job failed")
    artifacts.save(ctx.run_id, ctx.task_id, node, result.text,
                   {"agent": result.agent, "provider": result.provider, "model": result.model, "role": role})
    sessions = {result.session_key: result.session} if result.session_key and result.session else {}
    tasks.save_sessions(ctx.task_id, sessions)
    tasks.add_changed_files(ctx.task_id, result.changed_files)
    updates = {"outputs": {node: result.text}, "sessions": sessions, "changed_files": result.changed_files,
               "seq": seq + 1, "jobs": state.get("jobs", 0) + 1, "human_answer": None}
    if result.needs_human:
        updates["human"] = {"kind": "human_required", "node": node, "role": role, **result.needs_human}
    return updates
