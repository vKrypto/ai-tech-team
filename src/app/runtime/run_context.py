"""Run-scoped values derived from workflow state (ids, epoch, policy)."""
from dataclasses import dataclass

from ..orchestration.execution_policy import policy
from ..persistence.store import redis

EPOCH_KEY = "ait:run:{run_id}:epoch"


def epoch(run_id: str) -> int:
    return int(redis().get(EPOCH_KEY.format(run_id=run_id)) or 0)


def bump_epoch(run_id: str) -> int:
    """New epoch = new job ids, so re-executed nodes really run again instead of reusing old results."""
    return redis().incr(EPOCH_KEY.format(run_id=run_id))


@dataclass
class RunContext:
    task_id: int
    run_id: str
    workflow: str

    @classmethod
    def of(cls, state: dict) -> "RunContext":
        return cls(state["task_id"], state["run_id"], state.get("workflow", ""))

    @property
    def policy(self) -> dict:
        return policy(self.workflow)

    def job_id(self, node: str, seq: int, attempt: int = 0) -> str:
        return f"{self.run_id}:e{epoch(self.run_id)}:{node}:{seq}:{attempt}"
