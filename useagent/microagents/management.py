from pathlib import Path

import useagent
from useagent.microagents.microagent import MicroAgent, load_microagent


def _get_project_root() -> Path:
    return Path(useagent.__file__).resolve().parents[1]


def _get_default_microagent_directory() -> Path:
    return _get_project_root() / "microagents"


def load_microagents(dir_path: str) -> list[MicroAgent]:
    results: [MicroAgent] = []
    for path in Path(dir_path).rglob("*.microagent.md"):
        if path.name.count(".") >= 2 and path.name.endswith(".microagent.md"):
            results.append(load_microagent(path))
    return results


@staticmethod
def load_microagents_from_project_dir() -> list[MicroAgent]:
    return load_microagents(_get_default_microagent_directory())
