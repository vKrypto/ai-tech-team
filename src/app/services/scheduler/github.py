"""github-scheduler: watches repos (AI_TEAM_GITHUB_WATCH_REPOS) and turns new pull requests into pr_review
tasks. Each PR head commit is reviewed once: a new push to the PR creates a new review task."""
import json
import logging
import subprocess

from pymongo.errors import DuplicateKeyError

from ... import constants as C
from ...domain.enums import Source
from ...persistence.store import db, now
from ...settings import settings
from ...tools.filesystem.read import list_projects
from . import dashboard

log = logging.getLogger(__name__)
FIELDS = "number,title,url,headRefOid,isDraft,author"


def _open_prs(repo: str) -> list[dict]:
    args = ["gh", "pr", "list", "-R", repo, "--state", "open", "--json", FIELDS, "--limit", "50"]
    if settings.github_watch_filter == "review-requested":
        args += ["--search", "review-requested:@me"]
    r = subprocess.run(args, capture_output=True, text=True, timeout=60)
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[:300])
    return [p for p in json.loads(r.stdout or "[]") if not p.get("isDraft")]


def poll() -> int:
    created = 0
    projects = set(list_projects())
    for repo in settings.github_watch_repos:
        try:
            prs = _open_prs(repo)
        except Exception as e:
            log.warning("github poll of %s failed: %s", repo, e)
            continue
        name = repo.split("/")[-1]
        for pr in prs:
            key = f"{repo}#{pr['number']}@{pr['headRefOid'][:12]}"
            try:
                db()[C.C_GITHUB].insert_one({"_id": key, "repo": repo, "number": pr["number"], "seen_at": now()})
            except DuplicateKeyError:
                continue
            text = (f"Review pull request {repo}#{pr['number']}: {pr['title']}\n{pr['url']}\n"
                    f"(author: {(pr.get('author') or {}).get('login', '?')}, head {pr['headRefOid'][:12]})")
            task = dashboard.submit(text, Source.GITHUB, key, name if name in projects else None)
            db()[C.C_GITHUB].update_one({"_id": key}, {"$set": {"task_id": task["id"]}})
            created += 1
    return created
