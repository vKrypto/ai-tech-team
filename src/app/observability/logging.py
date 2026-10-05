import logging
import sys

from ..settings import settings


def setup(service: str, level: str = "INFO") -> None:
    logging.basicConfig(
        level=level, stream=sys.stdout, force=True,
        format=f"%(asctime)s %(levelname)s [{service}@{settings.host}] %(name)s: %(message)s")
    for noisy in ("httpx", "httpcore", "pymongo", "redisvl", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
