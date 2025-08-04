from pathlib import Path
from typing import Any

from loguru import logger
from pydantic.dataclasses import dataclass

from useagent.pydantic_models.info.environment import Commands, Environment, GitStatus
from useagent.pydantic_models.info.package import Package


@dataclass(frozen=False)
class PartialEnvironment:
    """
    Helper Class that we use to construct a running environment,
    without using (or corrupting) the Upstream TaskState.
    Unlike the normal Environment, this dataclass is mutable, intended to be build step-by-step.
    """

    project_root: Path | None = None
    git_status: GitStatus | None = None
    commands: Commands | None = None
    packages: list[Package] | None = None

    def __setattr__(self, key: str, value: Any) -> None:
        # There have been some issues about the the environment building and the management within deps.
        # This is a smaller change that will print changes to Debug Logging, so we can see after which Tool Call it was changed.
        if key in {"project_root", "git_status", "commands", "packages"}:
            logger.info(f"[MODEL] PartialEnvironment {key} set to {value!r}")
        super().__setattr__(key, value)

    def is_complete(self) -> bool:
        return all(
            [
                self.project_root,
                self.git_status,
                self.commands,
                self.packages,
            ]
        )

    def to_environment(self) -> Environment:
        #  DevNote: The Environment Constructor will manage all value errors and validations.
        assert self.is_complete()
        return Environment(
            # We can Pyright Ignore them, because is_complete() does the check for us
            project_root=self.project_root,  # pyright: ignore[reportArgumentType]
            git_status=self.git_status,  # pyright: ignore[reportArgumentType]
            commands=self.commands,  # pyright: ignore[reportArgumentType]
            packages=self.packages,  # pyright: ignore[reportArgumentType]
        )

    def get_missing_fields(self: "PartialEnvironment") -> list[str]:
        # Used to report in ValueErrors and help steer the agents.
        return [
            field
            for field in ("project_root", "git_status", "commands", "packages")
            if getattr(self, field) is None
        ]
