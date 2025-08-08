from io import StringIO
from pathlib import Path

import pytest

from useagent.pydantic_models.info.environment import Environment, GitStatus
from useagent.pydantic_models.info.package import Package
from useagent.pydantic_models.info.partial_environment import PartialEnvironment

# ---------- Fixtures ----------


@pytest.fixture
def forty_char_hex() -> str:
    # Valid-looking 40-char hex to satisfy HexCommit constraints
    return "a" * 40


@pytest.fixture
def dummy_packages() -> list[Package]:
    package = Package(name="example", version="1.0.0", source="apt")
    return [package]


@pytest.fixture
def minimal_complete_env_kwargs(forty_char_hex, dummy_packages):
    """
    Minimal set of kwargs to make PartialEnvironment complete
    under the new rules:
      - project_root set
      - all git fields set (not None)
      - at least one command present (we'll use build_command)
      - packages is a non-empty list
    """
    return dict(
        project_root=Path("."),
        active_git_commit=forty_char_hex,
        active_git_commit_is_head=True,
        active_git_branch="main",
        has_uncommited_changes=False,
        build_command="make build",
        packages=dummy_packages,
    )


# ---------- Tests ----------


@pytest.mark.pydantic_model
def test_is_complete_should_return_false_initially():
    pe = PartialEnvironment()
    assert not pe.is_complete()


@pytest.mark.pydantic_model
def test_is_complete_should_return_true_when_filled(minimal_complete_env_kwargs):
    pe = PartialEnvironment(**minimal_complete_env_kwargs)
    assert pe.is_complete()


@pytest.mark.pydantic_model
def test_get_missing_fields_should_list_all_initially():
    pe = PartialEnvironment()
    assert set(PartialEnvironment.get_missing_fields(pe)) == {
        "project_root",
        "active_git_commit",
        "active_git_commit_is_head",
        "active_git_branch",
        "has_uncommited_changes",
        "commands",
        "packages",
    }


@pytest.mark.pydantic_model
def test_get_missing_fields_should_list_only_remaining(forty_char_hex):
    # Set all git fields, leave others missing
    pe = PartialEnvironment(
        active_git_commit=forty_char_hex,
        active_git_commit_is_head=False,
        active_git_branch="main",
        has_uncommited_changes=False,
    )
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
def test_to_environment_should_return_environment_instance(minimal_complete_env_kwargs):
    pe = PartialEnvironment(**minimal_complete_env_kwargs)
    env = pe.to_environment()
    assert isinstance(env, Environment)

    # Spot-check the translated pieces
    assert isinstance(env.git_status, GitStatus)
    assert env.git_status.active_git_branch == "main"
    assert env.git_status.active_git_commit_is_head is True
    assert env.git_status.has_uncommited_changes is False

    # Commands should include our single provided command
    assert env.commands.build_command == "make build"

    # Packages should be preserved
    assert len(env.packages) == 1
    assert env.packages[0].name == "example"


def test_setattr_should_log_changes():
    log_output = StringIO()
    from loguru import logger

    token = logger.add(log_output, level="INFO")
    env = PartialEnvironment()
    env.project_root = Path("/tmp")
    logger.remove(token)

    logs = log_output.getvalue()
    assert "project_root" in logs
