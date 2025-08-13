import subprocess
from pathlib import Path

from useagent.state.git_repo import GitRepository


class Task:
    """
    Base Class for all Tasks, providing default

    For now, we require all Tasks to be Git Related.
    """

    uid: str
    git_repo: GitRepository

    def setup_project(self) -> None:
        git_cmd = (
            f"git config --global --add safe.directory {self.get_working_directory()}"
        )
        subprocess.run(
            git_cmd,
            shell=True,
            check=True,
            cwd=self.get_working_directory(),
        )
        # Subclasses might want to add more logic

    def reset_project(self):
        self.git_repo.repo_clean_changes()

    def get_working_directory(self) -> Path:
        raise NotImplementedError("Subclasses need to implement this")

    def get_issue_statement(self) -> str:
        raise NotImplementedError("Subclasses need to implement this")

    def command_transformer(self, command: str) -> str:
        """
        Transform a plain terminal command into a command that can be run in the container.

        Subclasses might need to overwrite this, but the default behavior assumes there are no changes necessary.
        Example: The USEBench requires a conda environment, so all commands should be within the conda environment.
        """
        return command

    @classmethod
    def get_default_working_dir(cls) -> Path:
        raise NotImplementedError("Subclasses need to implement this")
