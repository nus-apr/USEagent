from dataclasses import field
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic.dataclasses import dataclass

from useagent.pydantic_models.common.constrained_types import NonEmptyStr
from useagent.pydantic_models.info.environment import (
    Commands,
    Environment,
    GitStatus,
    HexCommit,
)
from useagent.pydantic_models.info.package import Package


@dataclass(frozen=False)
class PartialEnvironment:
    """
    Helper Class that we use to construct a running environment,
    without using (or corrupting) the Upstream TaskState.
    Unlike the normal Environment, this dataclass is mutable, intended to be build step-by-step.
    """

    project_root: Path | None = None

    active_git_commit: HexCommit | None = None
    active_git_commit_is_head: bool | None = None
    active_git_branch: NonEmptyStr | None = None
    has_uncommited_changes: bool | None = None

    setup_command: NonEmptyStr | None = None
    build_command: NonEmptyStr | None = None
    test_command: NonEmptyStr | None = None
    run_command: NonEmptyStr | None = None
    linting_command: NonEmptyStr | None = None

    reducable_test_scope: bool = False
    example_reduced_test_command: NonEmptyStr | None = None

    can_install_system_packages: bool = False
    system_package_manager: NonEmptyStr | None = None

    can_install_project_packages: bool = False
    project_package_manager: NonEmptyStr | None = None

    other_important_commands: list[NonEmptyStr] = field(default_factory=list)

    packages: list[Package] | None = None

    def __setattr__(self, key: str, value: Any) -> None:
        # There have been some issues about the the environment building and the management within deps.
        # This is a smaller change that will print changes to Debug Logging, so we can see after which Tool Call it was changed.
        git_fields = {
            "active_git_commit",
            "active_git_commit_is_head",
            "active_git_branch",
            "has_uncommited_changes",
        }
        command_fields = {
            "setup_command",
            "build_command",
            "test_command",
            "run_command",
            "linting_command",
            "reducable_test_scope",
            "example_reduced_test_command",
            "can_install_system_packages",
            "system_package_manager",
            "can_install_project_packages",
            "project_package_manager",
            "other_important_commands",
        }
        loggable = (
            key in {"project_root", "packages"}
            or key in git_fields
            or key in command_fields
        )
        if loggable:
            logger.info(f"[MODEL] PartialEnvironment {key} set to {value!r}")
        super().__setattr__(key, value)

    def is_complete(self) -> bool:
        return len(self.get_missing_fields()) == 0

    def to_environment(self) -> Environment:
        #  DevNote: The Environment Constructor will manage all value errors and validations.
        assert self.is_complete()
        return Environment(
            # We can Pyright Ignore them, because is_complete() does the check for us
            project_root=self.project_root,  # pyright: ignore[reportArgumentType]
            git_status=GitStatus(
                active_git_commit=self.active_git_commit,
                active_git_commit_is_head=bool(self.active_git_commit_is_head),
                active_git_branch=self.active_git_branch,
                has_uncommited_changes=bool(self.has_uncommited_changes),
            ),
            commands=Commands(
                setup_command=self.setup_command,
                build_command=self.build_command,
                test_command=self.test_command,
                run_command=self.run_command,
                linting_command=self.linting_command,
                reducable_test_scope=self.reducable_test_scope,
                example_reduced_test_command=self.example_reduced_test_command,
                can_install_project_packages=self.can_install_project_packages,
                system_package_manager=self.system_package_manager,
                can_install_system_packages=self.can_install_system_packages,
                project_package_manager=self.project_package_manager,
                other_important_commands=self.other_important_commands,
            ),
            packages=self.packages,  # pyright: ignore[reportArgumentType]
        )

    def get_missing_fields(self: "PartialEnvironment") -> list[str]:
        missing: list[str] = []

        # project_root must be set
        if self.project_root is None:
            missing.append("project_root")

        # all git fields must be set
        if self.active_git_commit is None:
            missing.append("active_git_commit")
        if self.active_git_commit_is_head is None:
            missing.append("active_git_commit_is_head")
        if self.active_git_branch is None:
            missing.append("active_git_branch")
        if self.has_uncommited_changes is None:
            missing.append("has_uncommited_changes")

        # commands: at least ONE of the main command-related fields must be "set"
        command_values_set = any(
            [
                bool(self.setup_command),
                bool(self.build_command),
                bool(self.test_command),
                bool(self.run_command),
                bool(self.example_reduced_test_command),
                bool(self.other_important_commands),  # non-empty list counts as set
            ]
        )
        if not command_values_set:
            missing.append("commands")

        # packages: must be a non-empty list
        if self.packages is None or len(self.packages) == 0:
            missing.append("packages")

        return missing

    @classmethod
    def get_output_instructions(cls) -> str:
        return (
            "A PartialEnvironment has the following fields: \n"
            "\t- project_root: Absolute filesystem path to the project root.\n"
            "\t- active_git_commit: Full hex Git commit hash (e.g., 40 chars).\n"
            "\t - active_git_commit_is_head: True if the active commit is the branch HEAD.\n"
            "\t - active_git_branch: Current Git branch name (non-empty string).\n"
            "\t - has_uncommited_changes: True if the working tree has uncommitted changes.\n"
            "\t - setup_command: Command to prepare the environment (e.g., install deps).\n"
            "\t - build_command: Command to build the project.\n"
            "\t - test_command: Command to run the test suite.\n"
            "\t - run_command: Command to run the application.\n"
            "\t - linting_command: Command to run linters/formatters.\n"
            "\t - reducable_test_scope: True if tests can be run in a reduced scope.\n"
            "\t - example_reduced_test_command: Example command to run a reduced test subset.\n"
            "\t - can_install_system_packages: True if the agent may install system packages.\n"
            "\t - system_package_manager: System package manager name (e.g., apt, yum, brew).\n"
            "\t - can_install_project_packages: True if the agent may install project packages.\n"
            "\t - project_package_manager: Project package manager name (e.g., pip, poetry, mvn, npm, pnpm, yarn).\n"
            "\t - other_important_commands: List of additional important commands (strings).\n"
            "\t - packages: List of Package entries present in the environment.\n"
            "**requirements:** 'project_root' set; all Git fields set; at least one of "
            "'setup_command', 'build_command', 'test_command', 'run_command', "
            "'example_reduced_test_command', or non-empty 'other_important_commands' provided; "
            "'packages' is a non-empty list.\n"
            "\n" + Package.get_output_instructions()
        )
