#!/usr/bin/env python3
"""Run the whole platform locally in one process (no swarm): starts throwaway redis + mongo containers
if needed, then `python -m app all`. Uses .env, so set AI_TEAM_PROVIDERS (mock is free).

    python scripts/run_local.py [--agents 3] [--port 8765]
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTAINERS = {"ai-team-dev-redis": ("redis:8", "16379:6379", ["redis-server", "--appendonly", "yes"], {}),
              "ai-team-dev-mongo": ("mongo:8.2", "17017:27017", ["--wiredTigerCacheSizeGB", "0.25"],
                                    {"GLIBC_TUNABLES": "glibc.pthread.rseq=0"})}


def ensure(name, image, port, args, env):
    running = subprocess.run(["docker", "ps", "-q", "-f", f"name=^{name}$"], capture_output=True, text=True).stdout
    if running.strip():
        return
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    cmd = ["docker", "run", "-d", "--name", name, "-p", f"127.0.0.1:{port}"]
    for k, v in env.items():
        cmd += ["-e", f"{k}={v}"]
    subprocess.run(cmd + [image, *args], check=True, capture_output=True)
    print(f"started {name} ({image})")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--agents", type=int, default=3)
    p.add_argument("--port", type=int, default=8765)
    a = p.parse_args()
    for name, spec in CONTAINERS.items():
        ensure(name, *spec)
    time.sleep(2)
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "AI_TEAM_REDIS_URL": "redis://127.0.0.1:16379/0",
           "AI_TEAM_MONGO_URL": "mongodb://127.0.0.1:17017", "AI_TEAM_HTTP_PORT": str(a.port),
           "AI_TEAM_DATA_DIR": str(ROOT / "data" / "local")}
    print(f"dashboard: http://localhost:{a.port}")
    os.execvpe(sys.executable, [sys.executable, "-m", "app", "all", "--agents", str(a.agents)], env)


if __name__ == "__main__":
    main()
