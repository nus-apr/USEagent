from pathlib import Path

from pydantic.dataclasses import dataclass

from useagent.pydantic_models.info.package import Package


@dataclass(frozen=True)
class Environment:
    """
    Holds information of a given project at a given point in time.
    Some information are optional. Not every project has a build command (if its a script), etc.
    """

    # DevNote: The Environments fields are described in the system_prompt.md of the Probing Agent, so any adjustments should also be mirrored there.

    active_path: Path
    project_root: Path

    packages: list[Package]

    # We make git info mandatory (a) because of project focus, and (b) because we can assume that git must be installed and available
    active_git_commit: str
    active_git_commit_is_Head: bool
    active_git_branch: str
    has_uncommited_changes: bool

    build_command: str | None = None
    test_command: str | None = None
    run_command: str | None = None
    linting_command: str | None = None

    reducable_test_scope: bool = False
    example_reduced_test_command: str | None = None

    can_install_system_packages: bool = False
    system_package_manager: str | None = None

    can_install_project_packages: bool = False
    project_package_manager: str | None = None

    # TODO: Do we want to also gather some test information here, e.g. if there were already failing tests?
