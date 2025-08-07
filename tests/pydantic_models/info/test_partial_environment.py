from io import StringIO
from pathlib import Path

import pytest

from useagent.pydantic_models.info.environment import Commands, Environment, GitStatus
from useagent.pydantic_models.info.package import Package, Source
from useagent.pydantic_models.info.partial_environment import PartialEnvironment


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
    package = Package(name="example", version="1.0.0", source=Source.SYSTEM)
    return [package]


@pytest.mark.pydantic_model
def test_is_complete_should_return_false_initially():
    pe = PartialEnvironment()
    assert not pe.is_complete()


@pytest.mark.pydantic_model
def test_is_complete_should_return_true_when_filled(
    dummy_git_status, dummy_commands, dummy_packages
):
    pe = PartialEnvironment(
        project_root=Path("."),
        git_status=dummy_git_status,
        commands=dummy_commands,
        packages=dummy_packages,
    )
    assert pe.is_complete()


@pytest.mark.pydantic_model
def test_get_missing_fields_should_list_all_initially():
    pe = PartialEnvironment()
    assert set(PartialEnvironment.get_missing_fields(pe)) == {
        "project_root",
        "git_status",
        "commands",
        "packages",
    }


@pytest.mark.pydantic_model
def test_get_missing_fields_should_list_only_remaining(dummy_git_status):
    pe = PartialEnvironment(git_status=dummy_git_status)
    assert set(PartialEnvironment.get_missing_fields(pe)) == {
        "project_root",
        "commands",
        "packages",
    }


@pytest.mark.pydantic_model
def test_to_environment_should_fail_if_incomplete():
    pe = PartialEnvironment()
    with pytest.raises(AssertionError):
        pe.to_environment()


@pytest.mark.pydantic_model
def test_to_environment_should_return_environment_instance(
    dummy_git_status, dummy_commands, dummy_packages
):
    pe = PartialEnvironment(
        project_root=Path("."),
        git_status=dummy_git_status,
        commands=dummy_commands,
        packages=dummy_packages,
    )
    env = pe.to_environment()
    assert isinstance(env, Environment)
    assert env.git_status == dummy_git_status


def test_setattr_should_log_changes():
    log_output = StringIO()
    from loguru import logger

    token = logger.add(log_output, level="INFO")
    env = PartialEnvironment()
    env.project_root = Path("/tmp")
    logger.remove(token)

    logs = log_output.getvalue()
    assert "project_root" in logs
