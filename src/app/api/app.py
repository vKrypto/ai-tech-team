"""HTTP API + dashboard, served by the scheduler node."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from . import auth
from .routes import dashboard, health, notifications, runs, schedules, tasks

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="AI Team", version="2.1")
app.middleware("http")(auth.middleware)
for r in (auth.router, dashboard.router, tasks.router, runs.router, health.router, schedules.router,
          notifications.router):
    app.include_router(r)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})
