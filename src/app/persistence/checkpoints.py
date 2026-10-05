"""LangGraph checkpointer: workflow state lives in Redis (AOF-persisted), one thread per run.

That is what makes the engine durable: after a crash a run resumes from its last finished node,
a held run resumes with the human's answer, and any node can be re-executed from history.
"""
from ..settings import settings

_saver = None


def get():
    global _saver
    if _saver is None:
        from langgraph.checkpoint.redis import RedisSaver
        _saver = RedisSaver(redis_url=settings.redis_url)
        _saver.setup()
    return _saver


def use(saver) -> None:
    global _saver
    _saver = saver
