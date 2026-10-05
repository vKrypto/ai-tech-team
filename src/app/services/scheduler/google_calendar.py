"""google-calendar-scheduler: polls Google Calendar (the calendar's secret iCal address, no OAuth needed)
and turns events tagged "[ai]" into tasks when they start. Title = task, description = details."""
import logging
from datetime import timedelta

import httpx
import icalendar
import recurring_ical_events
from pymongo.errors import DuplicateKeyError

from ... import constants as C
from ...domain.enums import Source
from ...persistence.store import db, now
from ...settings import settings
from . import dashboard

log = logging.getLogger(__name__)
LOOKBACK = timedelta(hours=6)   # events that started while we were down still fire


def due_events(ics_text: str, start, end) -> list[dict]:
    cal = icalendar.Calendar.from_ical(ics_text)
    out = []
    for ev in recurring_ical_events.of(cal).between(start, end):
        summary = str(ev.get("SUMMARY", "")).strip()
        if settings.gcal_tag and settings.gcal_tag.lower() not in summary.lower():
            continue
        dt = ev.get("DTSTART").dt
        if not hasattr(dt, "hour"):   # all-day event: fire at the start of the day
            continue
        out.append({"uid": str(ev.get("UID")), "start": dt, "summary": summary,
                    "description": str(ev.get("DESCRIPTION", "")).strip()})
    return out


def text_for(ev: dict) -> str:
    title = ev["summary"]
    if settings.gcal_tag:
        title = title.replace(settings.gcal_tag, "").strip()
    return title + (f"\n\n{ev['description']}" if ev["description"] else "")


def poll() -> int:
    created = 0
    ts = now()
    for url in settings.gcal_ics_urls:
        try:
            r = httpx.get(url, timeout=30, follow_redirects=True)
            r.raise_for_status()
            events = due_events(r.text, ts - LOOKBACK, ts)
        except Exception as e:
            log.warning("calendar fetch failed: %s", e)
            continue
        for ev in events:
            key = f"{ev['uid']}@{ev['start'].isoformat()}"
            try:  # the unique _id makes each occurrence fire exactly once
                db()[C.C_CALENDAR].insert_one({"_id": key, "summary": ev["summary"], "seen_at": ts})
            except DuplicateKeyError:
                continue
            task = dashboard.submit(text_for(ev), Source.GOOGLE_CALENDAR, key)
            db()[C.C_CALENDAR].update_one({"_id": key}, {"$set": {"task_id": task["id"]}})
            created += 1
    return created
