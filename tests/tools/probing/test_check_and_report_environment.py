from pathlib import Path

import pytest

from useagent.pydantic_models.info.environment import Commands, Environment, GitStatus
from useagent.pydantic_models.info.package import Package
from useagent.pydantic_models.info.partial_environment import PartialEnvironment
from useagent.tools.probing import _report_environment


@pytest.fixture
def forty_char_hex() -> str:
    # Valid-looking hex to satisfy HexCommit constraints
    return "a" * 15


@pytest.fixture
def dummy_packages() -> list[Package]:
    return [Package(name="example", version="1.0.0", source="apt")]


@pytest.fixture
def minimal_complete_env_kwargs(forty_char_hex, dummy_packages):
    """
    Minimal kwargs to make PartialEnvironment 'complete' under new rules:
      - project_root set
      - all git fields set (not None)
      - at least one command present (use build_command)
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


@pytest.mark.tool
def test_report_environment_should_fail_if_incomplete():
    # Missing: project_root, all git fields, commands, packages
    pe = PartialEnvironment()
    with pytest.raises(ValueError) as exc:
        _report_environment(pe)
    assert "missing entries" in str(exc.value).lower()


@pytest.mark.tool
def test_report_environment_should_succeed_if_complete(minimal_complete_env_kwargs):
    pe = PartialEnvironment(**minimal_complete_env_kwargs)
    env = _report_environment(pe)
    assert isinstance(env, Environment)

    # Spot-check Git status
    assert isinstance(env.git_status, GitStatus)
    assert env.git_status.active_git_branch == "main"
    assert env.git_status.active_git_commit_is_head is True
    assert env.git_status.has_uncommited_changes is False

    # Spot-check Commands
    assert isinstance(env.commands, Commands)
    assert env.commands.build_command == "make build"

    # Packages propagate
    assert len(env.packages) == 1
    assert env.packages[0].name == "example"


@pytest.mark.tool
def test_report_environment_should_fail_if_only_linting_command_set(
    forty_char_hex, dummy_packages
):
    # Linting alone should NOT satisfy the "at least one command" rule
    pe = PartialEnvironment(
        project_root=Path("."),
        active_git_commit=forty_char_hex,
        active_git_commit_is_head=False,
        active_git_branch="dev",
        has_uncommited_changes=True,
        linting_command="ruff check .",
        packages=dummy_packages,
    )
    with pytest.raises(ValueError) as exc:
        _report_environment(pe)
    assert "missing entries" in str(exc.value).lower()
    # Specifically we expect "commands" to be the blocker
    assert "commands" in str(exc.value).lower()


@pytest.mark.tool
def test_report_environment_should_succeed_with_other_important_commands_only(
    forty_char_hex, dummy_packages
):
    # No primary commands, but other_important_commands non-empty -> OK
    pe = PartialEnvironment(
        project_root=Path("."),
        active_git_commit=forty_char_hex,
        active_git_commit_is_head=True,
        active_git_branch="main",
        has_uncommited_changes=False,
        other_important_commands=["make clean"],
        packages=dummy_packages,
    )
    env = _report_environment(pe)
    assert isinstance(env, Environment)
    assert "make clean" in (env.commands.other_important_commands or [])


@pytest.mark.tool
def test_report_environment_should_succeed_with_example_reduced_test_command_only(
    forty_char_hex, dummy_packages
):
    # Using example_reduced_test_command alone should count as "a command is set"
    pe = PartialEnvironment(
        project_root=Path("."),
        active_git_commit=forty_char_hex,
        active_git_commit_is_head=True,
        active_git_branch="feature/xyz",
        has_uncommited_changes=False,
        example_reduced_test_command="pytest -k smoke -q",
        packages=dummy_packages,
    )
    env = _report_environment(pe)
    assert isinstance(env, Environment)
    assert env.commands.example_reduced_test_command == "pytest -k smoke -q"
    # Ensure other primary commands remain unset
    assert env.commands.build_command is None
    assert env.commands.test_command is None
    assert env.commands.run_command is None
    assert env.commands.setup_command is None


@pytest.mark.tool
def test_report_environment_forms_real_env_with_full_field_set(
    forty_char_hex, dummy_packages
):
    """
    Explicitly verify that a 'partial' instance with all fields set
    is converted into a proper Environment by _report_environment.
    """
    pe = PartialEnvironment(
        project_root=Path("/repo"),
        active_git_commit=forty_char_hex,
        active_git_commit_is_head=True,
        active_git_branch="release",
        has_uncommited_changes=False,
        setup_command="make setup",
        build_command="make build",
        test_command="pytest -q",
        run_command="python -m app",
        linting_command="ruff check .",
        reducable_test_scope=True,
        example_reduced_test_command="pytest -k smoke -q",
        can_install_system_packages=True,
        system_package_manager="apt",
        can_install_project_packages=True,
        project_package_manager="pip",
        other_important_commands=["make clean", "make docs"],
        packages=dummy_packages,
    )

    env = _report_environment(pe)
    assert isinstance(env, Environment)

    assert env.git_status.active_git_commit == forty_char_hex
    assert env.git_status.active_git_commit_is_head is True
    assert env.git_status.active_git_branch == "release"
    assert env.git_status.has_uncommited_changes is False

    c = env.commands
    assert c.setup_command == "make setup"
    assert c.build_command == "make build"
    assert c.test_command == "pytest -q"
    assert c.run_command == "python -m app"
    assert c.linting_command == "ruff check ."
    assert c.reducable_test_scope is True
    assert c.example_reduced_test_command == "pytest -k smoke -q"
    assert c.can_install_system_packages is True
    assert c.system_package_manager == "apt"
    assert c.can_install_project_packages is True
    assert c.project_package_manager == "pip"
    assert c.other_important_commands == ["make clean", "make docs"]

    assert len(env.packages) == 1
    assert env.packages[0].name == "example"
