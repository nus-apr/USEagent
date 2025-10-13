import os
from functools import lru_cache


@lru_cache(None)
def _in_docker() -> bool:
    """heuristic to detect if running inside docker container"""
    return os.path.exists("/.dockerenv")


# precedence: explicit env var wins; otherwise default to True in Docker, False elsewhere
USEBENCH_ENABLED: bool = (
    (os.getenv("USEBENCH_ENABLED") or "").lower() == "true"
    if os.getenv("USEBENCH_ENABLED") is not None
    else _in_docker()
)
