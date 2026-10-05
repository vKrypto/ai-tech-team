"""The broker: Redis Streams with consumer groups.

Delivery guarantees:
- A message is acked only after its handler returns, so if a process dies mid-work the message stays
  pending. On restart the consumer (same stable name, e.g. "engine-1") re-reads its own pending messages
  first; a message left by a consumer that never comes back is claimed by a peer once it has been idle
  for broker.claim_idle_seconds.
- Long handlers keep their messages "fresh" (XCLAIM to self every 30s) so peers don't steal live work.
- Poison messages are dropped after broker.max_deliveries attempts.
"""
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from pydantic import BaseModel
from redis.exceptions import ResponseError

from .. import constants as C
from ..persistence.store import redis
from ..settings import settings

log = logging.getLogger(__name__)


def publish(stream: str, payload: BaseModel | dict) -> str:
    data = payload.model_dump_json() if isinstance(payload, BaseModel) else json.dumps(payload, default=str)
    return redis().xadd(stream, {"data": data}, maxlen=settings.cfg("broker.stream_maxlen", 10000),
                        approximate=True)


def ensure_group(stream: str, group: str) -> None:
    try:
        redis().xgroup_create(stream, group, id="0", mkstream=True)
    except ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


class Consumer:
    def __init__(self, stream: str, group: str, handler: Callable[[dict], None], concurrency: int = 1,
                 name: str | None = None):
        self.stream, self.group, self.handler = stream, group, handler
        self.name = name or settings.host
        self.concurrency = max(1, concurrency)
        self.pool = ThreadPoolExecutor(self.concurrency, thread_name_prefix=f"{group}")
        self.inflight: set[str] = set()
        self.lock = threading.Lock()
        self.idle_ms = int(settings.cfg("broker.claim_idle_seconds", 600) * 1000)
        self.max_deliveries = settings.cfg("broker.max_deliveries", 5)

    @property
    def busy(self) -> int:
        return len(self.inflight)

    def run(self, stop: threading.Event) -> None:
        ensure_group(self.stream, self.group)
        threading.Thread(target=self._keepalive, args=(stop,), daemon=True, name=f"{self.group}-keepalive").start()
        self._read("0")  # own pending messages from before a restart
        while not stop.is_set():
            free = self.concurrency - self.busy
            if free <= 0:
                stop.wait(0.5)
                continue
            try:
                if not self._claim(free):
                    self._read(">", block=2000, count=free)
            except Exception:
                log.exception("consumer loop error on %s", self.stream)
                stop.wait(2)
        self.pool.shutdown(wait=False, cancel_futures=True)

    def _read(self, last_id: str, block: int | None = None, count: int | None = None) -> None:
        resp = redis().xreadgroup(self.group, self.name, {self.stream: last_id}, count=count or 100, block=block)
        for _, messages in resp or []:
            for msg_id, fields in messages:
                self._submit(msg_id, fields)

    def _claim(self, count: int) -> bool:
        """Take over messages a dead peer left pending."""
        resp = redis().xautoclaim(self.stream, self.group, self.name, min_idle_time=self.idle_ms, start_id="0-0",
                                  count=count)
        messages = resp[1] if resp else []
        for msg_id, fields in messages:
            if fields:  # None = deleted entry
                log.warning("claimed idle message %s from a peer", msg_id)
                self._submit(msg_id, fields)
            else:
                redis().xack(self.stream, self.group, msg_id)
        return bool(messages)

    def _submit(self, msg_id: str, fields: dict) -> None:
        with self.lock:
            if msg_id in self.inflight:
                return
            self.inflight.add(msg_id)
        self.pool.submit(self._handle, msg_id, fields)

    def _handle(self, msg_id: str, fields: dict) -> None:
        key = C.KEY_DELIVERIES.format(stream=self.stream, msg_id=msg_id)
        try:
            n = redis().incr(key)
            redis().expire(key, 7 * 24 * 3600)
            if n > self.max_deliveries:
                log.error("dropping %s on %s after %s deliveries: %s", msg_id, self.stream, n - 1, fields)
            else:
                t0 = time.monotonic()
                payload = json.loads(fields.get("data") or "{}")
                log.info("%s %s: handling %s (delivery %s)", self.stream, msg_id,
                         {k: payload[k] for k in ("kind", "task_id", "job_id", "node", "status") if k in payload}, n)
                self.handler(payload)
                log.info("%s %s: done in %.1fs", self.stream, msg_id, time.monotonic() - t0)
        except Exception:
            # Handlers record failures on the task themselves; an exception here is a bug. Ack anyway so
            # it can't loop forever; it is logged with the payload.
            log.exception("handler failed for %s on %s: %s", msg_id, self.stream, fields)
        finally:
            redis().xack(self.stream, self.group, msg_id)
            redis().delete(key)
            with self.lock:
                self.inflight.discard(msg_id)

    def _keepalive(self, stop: threading.Event) -> None:
        while not stop.wait(30):
            with self.lock:
                ids = list(self.inflight)
            if ids:
                try:
                    redis().xclaim(self.stream, self.group, self.name, min_idle_time=0, message_ids=ids,
                                   justid=True)
                except Exception:
                    log.exception("keepalive failed")
