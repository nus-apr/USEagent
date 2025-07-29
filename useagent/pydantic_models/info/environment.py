from dataclasses import field
from pathlib import Path

from pydantic import constr, field_validator, model_validator
from pydantic.dataclasses import dataclass

from useagent.pydantic_models.common.constrained_types import NonEmptyStr
from useagent.pydantic_models.info.package import Package

HexCommit = constr(
    strip_whitespace=True, min_length=7, max_length=40, pattern="^[0-9a-fA-F]+$"
)


@dataclass(frozen=True)
class GitStatus:
    """
    Info on the current git status.
    active_git_commit should be a minimum of 8 hexadecimal characters of the commits.
    """

    active_git_commit: HexCommit
    active_git_commit_is_head: bool
    active_git_branch: NonEmptyStr
    has_uncommited_changes: bool

    @field_validator("active_git_branch")
    @classmethod
    def validate_git_branch(cls, v: str) -> str:
        if any(
            [
                v.startswith("/"),
                v.endswith("/"),
                "//" in v,
                ".." in v,
                v == "@",
                v.endswith(".lock"),
            ]
        ):
            raise ValueError(f"Invalid git branch name: {v}")
        return v


@dataclass
class Commands:
    """
    Info on the most relevant commands.
    """

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

    @model_validator(mode="after")
    def check_at_least_one_command(self) -> "Commands":
        command_fields = [
            self.build_command,
            self.test_command,
            self.run_command,
            self.linting_command,
            self.example_reduced_test_command,
            self.system_package_manager,
            self.project_package_manager,
        ]
        if all(v is None for v in command_fields) and not self.other_important_commands:
            raise ValueError(
                "No commands found: at least one command or other_important_commands must be present"
            )
        return self

    @model_validator(mode="after")
    def remove_duplicates_from_other_commands(self) -> "Commands":
        known = {
            self.build_command,
            self.test_command,
            self.run_command,
            self.linting_command,
            self.example_reduced_test_command,
            self.system_package_manager,
            self.project_package_manager,
        }
        known_cleaned = {cmd.strip() for cmd in known if cmd}
        self.other_important_commands = [
            cmd
            for cmd in self.other_important_commands
            if cmd.strip() not in known_cleaned
        ]
        return self


@dataclass(frozen=True)
class Environment:
    """
    Holds information of a given project at a given point in time.
    Some information are optional. Not every project has a build command (if its a script), etc.
    """

    # DevNote: The Environments fields are described in the system_prompt.md of the Probing Agent, so any adjustments should also be mirrored there.

    project_root: Path

    packages: list[Package]

    commands: Commands

    # We make git info mandatory (a) because of project focus, and (b) because we can assume that git must be installed and available
    git_status: GitStatus

    def __str__(self) -> str:
        return (
            f"Environment("
            f"project_root={self.project_root}, "
            f"packages={[p.name for p in self.packages]}, "
            f"commands={self.commands}, "
            f"git_status={self.git_status})"
        )
