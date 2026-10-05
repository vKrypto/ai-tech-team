"""python -m app <service>

  scheduler | orchestrator | engine | agent | notifier   one component (what each stack service runs)
  all [--agents N]                                       every component in one process (local dev)
  health                                                 container healthcheck (heartbeat file age)
"""
import argparse
import os
import signal
import sys
import threading
import time

from . import constants as C


def _health() -> int:
    try:
        return 0 if time.time() - os.path.getmtime(C.HEALTH_FILE) < 60 else 1
    except OSError:
        return 1


def main() -> None:
    p = argparse.ArgumentParser(prog="app", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("service", choices=["scheduler", "orchestrator", "engine", "agent", "notifier", "all", "health"])
    p.add_argument("--agents", type=int, default=3, help="agent workers for `all`")
    args = p.parse_args()
    if args.service == "health":
        sys.exit(_health())

    from . import bootstrap
    bootstrap.init(args.service)
    kinds = bootstrap.services()
    if args.service != "all":
        kinds[args.service]().start()
        return

    from .settings import settings
    bootstrap.ready()
    stop = threading.Event()
    plan = ["notifier", "orchestrator", "engine", *["agent"] * args.agents, "scheduler"]
    for i, kind in enumerate(plan):
        svc = kinds[kind](name=f"{settings.host}-{kind}-{i}")
        svc.stop = stop
        threading.Thread(target=svc.start, kwargs={"install_signals": False}, daemon=True, name=kind).start()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    stop.wait()
