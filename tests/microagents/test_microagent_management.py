import tempfile
from pathlib import Path

import pytest

from useagent.microagents.management import (
    _get_default_microagent_directory,
    _get_project_root,
    load_microagents,
)
from useagent.microagents.microagent import MicroAgent


def test_get_project_root_is_not_empty():
    root = _get_project_root()
    assert root.exists()
    assert root.name != ""


def test_get_default_microagent_directory():
    default_dir = _get_default_microagent_directory()
    assert isinstance(default_dir, Path)
    assert "microagents" in str(default_dir)


def test_load_microagents_with_valid_file_name_but_wrong_file_format():
    with tempfile.TemporaryDirectory() as tmpdir:
        dir_path = Path(tmpdir)
        file_path = dir_path / "sample.microagent.md"
        file_path.write_text(
            "# invalid microagent format\n\nName: test\nDescription: just a test\n"
        )
        with pytest.raises(ValueError):
            load_microagents(str(dir_path))


def test_load_microagents_ignores_invalid_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        dir_path = Path(tmpdir)
        (dir_path / "ignore.txt").write_text("not a microagent")
        (dir_path / "wrong.agent.md").write_text("invalid")

        agents = load_microagents(str(dir_path))
        assert agents == []


def test_load_microagents_from_default_directory():
    dir_path = _get_default_microagent_directory()
    agents = load_microagents(str(dir_path))
    assert isinstance(agents, list)
    assert len(agents) > 0
    assert all(isinstance(agent, MicroAgent) for agent in agents)
