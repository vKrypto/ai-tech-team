"""Task execution workflow (generic):

  receive_task -> understand_task -> plan_task -> select_agent -> execute_agent | research | coding | validation
                                                      ^                                   |
                                                      |                            validate_result
                                                      +---- next step --------------------+
                                                      +---- replan <-- failed ------------+
                                                                       all done ---> complete -> finalize
"""
from ..factory import GraphBuilder
from .nodes.complete import complete
from .nodes.execute_agent import execute_agent
from .nodes.plan_task import plan_task
from .nodes.receive_task import receive_task
from .nodes.replan import replan
from .nodes.select_agent import select_agent
from .nodes.understand_task import understand_task
from .nodes.validate_result import validate_result
from .routes import after_select, after_validate
from .subgraphs import coding_graph, research_graph, validation_graph

EXECUTORS = ["execute_agent", "research", "coding", "validation"]


def build(checkpointer=None):
    b = GraphBuilder()
    b.node("receive_task", receive_task).node("understand_task", understand_task).node("plan_task", plan_task) \
        .node("select_agent", select_agent).node("execute_agent", execute_agent) \
        .subgraph("research", research_graph.subgraph()).subgraph("coding", coding_graph.subgraph()) \
        .subgraph("validation", validation_graph.subgraph()) \
        .node("validate_result", validate_result).node("replan", replan).node("complete", complete)
    b.start("receive_task").then("receive_task", "understand_task").then("understand_task", "plan_task") \
        .then("plan_task", "select_agent").then("select_agent", after_select, EXECUTORS)
    for ex in EXECUTORS:
        b.then(ex, "validate_result")
    b.then("validate_result", after_validate, ["select_agent", "replan", "complete"]) \
        .then("replan", "select_agent").then("complete", "finalize")
    b.finalize()
    return b.build(checkpointer, name="task_execution")


graph = build()
