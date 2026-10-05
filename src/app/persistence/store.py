"""Shared clients: MongoDB (durable task store) and Redis (broker, state, checkpoints).

Clients are created lazily; tests swap them with `use(db=..., redis=...)`.
"""
import logging
import time
from datetime import datetime, timezone

from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
from redis import Redis

from .. import constants as C
from ..settings import settings

log = logging.getLogger(__name__)
_db = None
_redis: Redis | None = None


def now() -> datetime:
    return datetime.now(timezone.utc)


def db():
    global _db
    if _db is None:
        client = MongoClient(settings.mongo_url, serverSelectionTimeoutMS=5000, tz_aware=True)
        _db = client[settings.mongo_db]
    return _db


def redis() -> Redis:
    global _redis
    if _redis is None:
        # socket timeout must exceed the longest blocking call (BLPOP 5s, XREADGROUP 2s)
        _redis = Redis.from_url(settings.redis_url, decode_responses=True, health_check_interval=30,
                                socket_timeout=30, socket_connect_timeout=10, retry_on_timeout=True)
    return _redis


def use(db=None, redis=None) -> None:
    global _db, _redis
    if db is not None:
        _db = db
    if redis is not None:
        _redis = redis


def next_id(name: str) -> int:
    doc = db()[C.C_COUNTERS].find_one_and_update(
        {"_id": name}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER)
    return doc["seq"]


def ping() -> None:
    redis().ping()
    db().command("ping")


def wait_ready(timeout: float = 120) -> None:
    """Block until Redis and Mongo answer (swarm starts services in no particular order)."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            ping()
            return
        except Exception as e:
            if time.monotonic() > deadline:
                raise
            log.info("waiting for redis/mongo: %s", e)
            time.sleep(2)


def ensure_indexes() -> None:
    d = db()
    d[C.C_TASKS].create_index([("status", ASCENDING), ("updated_at", DESCENDING)])
    d[C.C_TASKS].create_index([("project", ASCENDING)])
    d[C.C_MESSAGES].create_index([("task_id", ASCENDING), ("turn", ASCENDING)])
    d[C.C_EVENTS].create_index([("task_id", ASCENDING), ("seq", ASCENDING)])
    d[C.C_RUNS].create_index([("task_id", ASCENDING)])
    d[C.C_ARTIFACTS].create_index([("run_id", ASCENDING), ("node", ASCENDING)])
    d[C.C_NOTIFICATIONS].create_index([("read", ASCENDING), ("created_at", DESCENDING)])
    d[C.C_MEMORIES].create_index([("project", ASCENDING), ("created_at", DESCENDING)])
