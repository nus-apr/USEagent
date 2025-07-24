from pathlib import Path

import useagent
from useagent.microagents.microagent import MicroAgent, load_microagent

# Simple `Cache` that we only load things once. There should never be changes to the MicroAgents during Runtime.
_dict_microagents: dict[str, list[MicroAgent]] = {}


def _get_project_root() -> Path:
    return Path(useagent.__file__).resolve().parents[1]


def _get_default_microagent_directory() -> Path:
    return _get_project_root() / "microagents"


def load_microagents(dir_path: str) -> list[MicroAgent]:
    if dir_path in _dict_microagents.keys():
        return _dict_microagents[dir_path]

    results: list[MicroAgent] = []
    for path in Path(dir_path).rglob("*.microagent.md"):
        if path.name.count(".") >= 2 and path.name.endswith(".microagent.md"):
            results.append(load_microagent(path))
    _dict_microagents[dir_path] = results
    return results


@staticmethod
def load_microagents_from_project_dir() -> list[MicroAgent]:
    return load_microagents(str(_get_default_microagent_directory()))
