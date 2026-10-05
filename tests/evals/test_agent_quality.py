"""Routing quality of the keyword heuristic (the floor every provider must beat). For real providers run
scripts/evaluate.py, which uses whatever is enabled in .env."""
import json
from pathlib import Path

from app.agents.orchestrator.policies import heuristic, normalize

DATA = Path(__file__).parent / "datasets" / "routing.jsonl"


def test_heuristic_baseline_routes_most_tasks():
    rows = [json.loads(l) for l in DATA.read_text().splitlines() if l.strip()]
    hits = sum(normalize(heuristic(r["text"], ["demo-app"]), ["demo-app"]).workflow == r["workflow"] for r in rows)
    assert hits / len(rows) >= 0.75
