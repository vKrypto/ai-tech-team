#!/usr/bin/env python3
"""Routing eval: how well does the orchestrator understand tasks? Runs tests/evals/datasets/routing.jsonl
through the orchestrator agent with the providers enabled in .env and reports accuracy.

    python scripts/evaluate.py [--dataset tests/evals/datasets/routing.jsonl]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def run(dataset: Path) -> dict:
    from app.agents.orchestrator.agent import understand
    rows = [json.loads(l) for l in dataset.read_text().splitlines() if l.strip()]
    projects = sorted({r["project"] for r in rows if r.get("project") not in (None, "general")} | {"demo-app"})
    score = {"workflow": 0, "task_type": 0, "project": 0, "n": len(rows), "misses": []}
    for r in rows:
        u, used = understand(r["text"], projects)
        for k in ("workflow", "task_type", "project"):
            if k in r and getattr(u, k) == r[k]:
                score[k] += 1
            elif k in r:
                score["misses"].append(f"{k}: {r['text'][:60]!r} -> {getattr(u, k)} (expected {r[k]}, by {used})")
    return score


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default=str(ROOT / "tests/evals/datasets/routing.jsonl"))
    s = run(Path(p.parse_args().dataset))
    for k in ("workflow", "task_type", "project"):
        print(f"{k:10s} {s[k]}/{s['n']}")
    print("\n".join(s["misses"]))
