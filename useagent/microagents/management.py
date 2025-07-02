from pathlib import Path
from typing import List,Callable

import useagent
from useagent.microagents.microagent import MicroAgent, load_microagent
from loguru import logger


def _get_project_root() -> Path:
    return Path(useagent.__file__).resolve().parents[1]

def _get_default_microagent_directory() -> Path:
    return _get_project_root() / "microagents"

def load_microagents(dir_path: str) -> List[MicroAgent]:
    results: [MicroAgent] = []
    for path in Path(dir_path).rglob("*.microagent.md"):
        if path.name.count('.') >= 2 and path.name.endswith(".microagent.md"):
            results.append(load_microagent(path))
    return results


# Example: __file__ is /some/path/a/b/c/module.py
# parents[0] = c, [1] = b, [2] = a, [3] = project root

if __name__ == "__main__":
    microagent_dir = _get_default_microagent_directory()
    microagents = load_microagents(microagent_dir)
    print("Found",len(microagents), " Microagents")