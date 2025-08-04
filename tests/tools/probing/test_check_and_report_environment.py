from pathlib import Path

import pytest

from useagent.pydantic_models.info.environment import Commands, Environment, GitStatus
from useagent.pydantic_models.info.package import Package, Source
from useagent.pydantic_models.info.partial_environment import PartialEnvironment
from useagent.tools.probing import _report_environment


@pytest.fixture
def dummy_git_status() -> GitStatus:
    return GitStatus(
        active_git_commit="abcdef12",
        active_git_commit_is_head=True,
        active_git_branch="main",
        has_uncommited_changes=False,
    )


@pytest.fixture
def dummy_commands() -> Commands:
    return Commands(build_command="make build")


@pytest.fixture
def dummy_packages() -> list[Package]:
    return [Package(name="example", version="1.0.0", source=Source.SYSTEM)]


@pytest.mark.tool
def test_report_environment_should_fail_if_incomplete():
    pe = PartialEnvironment(git_status=None)
    with pytest.raises(ValueError) as exc:
        _report_environment(pe)
    assert "missing entries" in str(exc.value)


@pytest.mark.tool
def test_report_environment_should_succeed_if_complete(
    dummy_git_status, dummy_commands, dummy_packages
):
    pe = PartialEnvironment(
        project_root=Path("."),
        git_status=dummy_git_status,
        commands=dummy_commands,
        packages=dummy_packages,
    )
    env = _report_environment(pe)
    assert isinstance(env, Environment)
    assert env.commands == dummy_commands
