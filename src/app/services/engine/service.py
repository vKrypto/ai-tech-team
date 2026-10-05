"""The workflow engine: consumes workflow commands (start / resume / rerun) and drives LangGraph runs.
Runs execute their nodes by dispatching agent jobs to the agent pool (status: processing)."""
import logging

from ... import constants as C
from ...domain.events import WorkflowCommand
from ...orchestration.dispatcher import Consumer
from ...runtime import graph_runner
from ...settings import settings
from ...workflows import registry
from ..common import Service

log = logging.getLogger(__name__)


class EngineService(Service):
    kind = "engine"

    def setup(self):
        for name in registry.names():   # compile eagerly: config errors surface at startup
            registry.compiled(name)
        self.consumer = Consumer(C.STREAM_WORKFLOWS, C.GROUP_ENGINE,
                                 lambda p: graph_runner.handle(WorkflowCommand(**p)),
                                 name=self.name, concurrency=settings.cfg("engine.max_parallel", 4))

    def status(self):
        return {"busy": self.consumer.busy, "capacity": self.consumer.concurrency}

    def run(self):
        self.consumer.run(self.stop)
