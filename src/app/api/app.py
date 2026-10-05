"""HTTP API + dashboard, served by the scheduler node."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from .routes import health, notifications, runs, schedules, tasks

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="AI Team", version="2.0")
for r in (tasks.router, runs.router, health.router, schedules.router, notifications.router):
    app.include_router(r)


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(STATIC / "index.html")
