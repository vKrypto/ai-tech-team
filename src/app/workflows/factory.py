"""Small builder so every workflow graph gets the same tracking, guards and recovery wiring."""
from langgraph.graph import END, START, StateGraph

from .common.context import CONTROL, guard, tracked
from .common.nodes.finalize import finalize
from .common.nodes.load_context import load_context
from .common.nodes.validate_task import validate_task
from .common.state import WorkflowState
from .common.subgraphs.recovery import add_recovery


class GraphBuilder:
    def __init__(self):
        self.g = StateGraph(WorkflowState)
        self.work: list[str] = []
        self.edges: list[tuple[str, str]] = []      # the workflow's real edges, for the UI diagram
        self.subs: dict[str, dict] = {}

    def node(self, name: str, fn) -> "GraphBuilder":
        self.g.add_node(name, tracked(name, fn))
        self.work.append(name)
        return self

    def subgraph(self, name: str, compiled) -> "GraphBuilder":
        self.g.add_node(name, compiled)
        self.work.append(name)
        self.subs[name] = compiled.ait_spec
        return self

    def start(self, first: str) -> "GraphBuilder":
        self.g.add_edge(START, first)
        self.edges.append((START, first))
        return self

    def then(self, src: str, nxt, destinations: list[str] | None = None) -> "GraphBuilder":
        dests = destinations or [nxt]
        self.g.add_conditional_edges(src, guard(nxt), [*dests, *CONTROL])
        self.edges += [(src, d) for d in dests]
        return self

    def head(self) -> "GraphBuilder":
        """validate_task -> load_context, for standalone workflows."""
        return self.node("validate_task", validate_task).node("load_context", load_context) \
            .start("validate_task").then("validate_task", "load_context")

    def finalize(self) -> "GraphBuilder":
        self.node("finalize", finalize)
        self.g.add_edge("finalize", END)
        self.edges.append(("finalize", END))
        return self

    def build(self, checkpointer=None, name: str | None = None):
        add_recovery(self.g, self.work)
        compiled = self.g.compile(checkpointer=checkpointer, name=name)
        compiled.ait_spec = {"nodes": list(self.work), "edges": list(self.edges), "subgraphs": self.subs}
        return compiled


def mermaid(spec: dict) -> str:
    """Clean diagram of a workflow: real edges only; approval/handle_error drawn once (any step can go there).
    Node ids: parent nodes by name, subgraph nodes as "<subgraph>__<node>"; the UI colours them by status."""
    lines = ["flowchart TD", "  __start__([start]):::terminal", "  __end__([end]):::terminal"]

    def emit(sp: dict, prefix: str, indent: str):
        for n in sp["nodes"]:
            if n in sp["subgraphs"]:
                lines.append(f"{indent}subgraph {prefix}{n} [{n}]")
                emit(sp["subgraphs"][n], f"{prefix}{n}__", indent + "  ")
                lines.append(f"{indent}end")
            else:
                lines.append(f"{indent}{prefix}{n}({n})")
        for a, b in sp["edges"]:
            src = f"{prefix}__start__" if a == START and prefix else a if a == START else f"{prefix}{a}"
            dst = f"{prefix}__end__" if b == END and prefix else b if b == END else f"{prefix}{b}"
            if prefix and a == START:
                continue  # entry into a subgraph is drawn as the edge into its box
            if prefix and b == END:
                continue
            lines.append(f"{indent}{src} --> {dst}")

    emit(spec, "", "  ")
    lines += ["  approval{{approval: human}}:::control", "  handle_error{{handle_error}}:::control",
              "  classDef terminal fill:none,stroke-dasharray:3 3",
              "  classDef control stroke-dasharray:4 3"]
    return "\n".join(lines)
