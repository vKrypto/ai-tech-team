from fastapi import APIRouter, HTTPException

from ... import constants as C
from ...persistence.store import db
from ...services.scheduler import cron
from ..schemas.task import NewSchedule

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


def _out(d):
    d = dict(d)
    d["id"] = d.pop("_id")
    return d


@router.get("")
def find():
    return [_out(d) for d in db()[C.C_SCHEDULES].find().sort("_id", 1)]


@router.post("", status_code=201)
def create(body: NewSchedule):
    try:
        return _out(cron.create(body.name, body.cron, body.text, body.project))
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.post("/{sid}/toggle")
def toggle(sid: int):
    d = db()[C.C_SCHEDULES].find_one({"_id": sid})
    if not d:
        raise HTTPException(404, "schedule not found")
    fields = {"enabled": not d["enabled"]}
    if fields["enabled"]:
        from ...orchestration.scheduler import next_run
        from ...persistence.store import now
        fields["next_run"] = next_run(d["cron"], now())
    db()[C.C_SCHEDULES].update_one({"_id": sid}, {"$set": fields})
    return _out({**d, **fields})


@router.delete("/{sid}", status_code=204)
def delete(sid: int):
    db()[C.C_SCHEDULES].delete_one({"_id": sid})
