"""PR review workflow (pr_reviewer + tester):

  validate_task -> load_context -> inspect_pr -> verify_pr -> review_pr -> post_review -> finalize
                                                                     (post_mode: none) --> finalize
"""
from ..factory import GraphBuilder
from .nodes.inspect_pr import inspect_pr
from .nodes.post_review import post_review
from .nodes.review_pr import review_pr
from .nodes.verify_pr import verify_pr
from .routes import after_review


def build(checkpointer=None):
    b = GraphBuilder().head()
    b.node("inspect_pr", inspect_pr).node("verify_pr", verify_pr).node("review_pr", review_pr) \
        .node("post_review", post_review)
    b.then("load_context", "inspect_pr").then("inspect_pr", "verify_pr").then("verify_pr", "review_pr") \
        .then("review_pr", lambda s: after_review(s, "finalize"), ["post_review", "finalize"]) \
        .then("post_review", "finalize")
    b.finalize()
    return b.build(checkpointer, name="pr_review")


graph = build()
