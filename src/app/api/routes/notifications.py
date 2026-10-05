from fastapi import APIRouter
from pymongo import DESCENDING

from ... import constants as C
from ...domain.events import Notification
from ...orchestration.dispatcher import publish
from ...persistence.store import db
from ...services.notifier.channels import registry as channels
from ...settings import settings

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _out(d):
    d = dict(d)
    d["id"] = d.pop("_id")
    return d


@router.get("")
def find(limit: int = 100):
    col = db()[C.C_NOTIFICATIONS]
    return {"unread": col.count_documents({"read": False}),
            "items": [_out(d) for d in col.find().sort("_id", DESCENDING).limit(limit)]}


@router.post("/{nid}/read")
def read(nid: int):
    db()[C.C_NOTIFICATIONS].update_one({"_id": nid}, {"$set": {"read": True}})
    return {"ok": True}


@router.post("/read-all")
def read_all():
    db()[C.C_NOTIFICATIONS].update_many({"read": False}, {"$set": {"read": True}})
    return {"ok": True}


@router.get("/channels")
def list_channels():
    return [c.describe() for c in channels.channels()]


@router.post("/test")
def test():
    """Send a test notification through every enabled channel (the notifier records the per-channel result)."""
    publish(C.STREAM_NOTIFICATIONS, Notification(
        event="test", level="info", title="AI Team test notification",
        message="If you can read this, the channel works.", link=settings.public_url))
    return {"queued": True, "channels": [c.name for c in channels.enabled() if c.accepts({"event": "test", "level": "info"})]}
