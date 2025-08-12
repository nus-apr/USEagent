import shutil
import os
from pathlib import Path

from useagent.state.git_repo import GitRepository
from useagent.tasks.task import Task


class LocalTask(Task):
    """
    Task for running Local Repositories.
    The files are copied into a temporary working directory,
    and if necessary a git repository is initialized.
    """

    project_path: str
    issue_statement: str
    uid: str = os.getenv("INSTANCE_ID", "local")
    _working_dir: Path  # All files will be copied to this directory, before the git repository is initialized there.

    def __init__(
        self,
        issue_statement: str,
        project_path: str,
        working_dir: Path = Path("/tmp/working_dir"),
    ):
        if not issue_statement:
            raise ValueError("issue_statement must be a non-empty string")
        if isinstance(issue_statement, str) and not issue_statement.strip():
            raise ValueError("issue_statement must be a non-empty string")
        if not project_path or (
            isinstance(project_path, str) and not project_path.strip()
        ):
            raise ValueError("project_path must be a non-empty string")

        if not Path(project_path).exists():
            raise ValueError(f"project_path '{project_path}' does not exist")
        if not working_dir:
            raise ValueError("working_dir must be a valid Path instance")

        self.project_path = project_path
        self.issue_statement = issue_statement
        self._working_dir = working_dir
        self.copy_project_to_working_dir()
        self.git_repo = GitRepository(local_path=str(self._working_dir))
        self.setup_project()

    def get_issue_statement(self) -> str:
        return self.issue_statement

    def get_working_directory(self) -> Path:
        return self._working_dir

    def copy_project_to_working_dir(self) -> None:
        if self._working_dir.exists():
            shutil.rmtree(self._working_dir)
        shutil.copytree(self.project_path, self._working_dir)
