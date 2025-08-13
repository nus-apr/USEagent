import re
import shutil
import subprocess
from pathlib import Path

from loguru import logger

from useagent.state.git_repo import GitRepository
from useagent.tasks.task import Task

_default_working_dir = Path("/tmp/working_dir")


class GithubTask(Task):
    """
    Task for cloning GitHub repositories into a working directory.
    """

    repo_url: str
    issue_statement: str
    uid: str
    _working_dir: Path
    commit: str | None = None
    _default_branch_name: str = "useagent"

    def __init__(
        self,
        issue_statement: str,
        repo_url: str,
        working_dir: Path = _default_working_dir,
        commit: str | None = None,
    ):
        if not issue_statement or not issue_statement.strip():
            raise ValueError("issue_statement must be a non-empty string")
        if not repo_url or not repo_url.strip():
            raise ValueError("repo_url must be a non-empty string")
        if not (
            repo_url.startswith("https://")
            or repo_url.startswith("git@")
            or repo_url.startswith("file://")
        ):
            raise ValueError("repo_url must be a valid SSH, HTTPS, or file Git URL")
        if not working_dir:
            raise ValueError("working_dir must be a valid Path instance")
        if commit is not None:
            if not isinstance(commit, str) or not re.fullmatch(
                r"[0-9a-fA-F]{7,40}", commit
            ):
                raise ValueError("commit must be a valid git SHA (7-40 hex characters)")

        logger.info(
            f"[Setup] Setting up Github Task, cloning {repo_url} into {working_dir}"
        )

        self.repo_url = repo_url
        self.commit = commit

        self.issue_statement = issue_statement
        self._working_dir = working_dir
        self.uid = self._derive_uid_from_url(repo_url)
        self.clone_repo_to_working_dir()
        self.git_repo = GitRepository(local_path=str(self._working_dir))
        self.setup_project()

    def get_issue_statement(self) -> str:
        return self.issue_statement

    def get_working_directory(self) -> Path:
        return self._working_dir

    def clone_repo_to_working_dir(self) -> None:
        # if self._working_dir.exists():
        #    subprocess.run(["rm", "-rf", str(self._working_dir)], check=True)
        if self._working_dir.exists():
            for item in self._working_dir.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()

        subprocess.run(
            ["git", "clone", self.repo_url, str(self._working_dir)], check=True
        )

    def setup_project(self) -> None:
        super().setup_project()

        if self.commit:
            logger.info(
                "[SETUP] Commit was specified for {self.uid}, checking out {self.commit} and branching into {self._default_branch_name} "
            )
            subprocess.run(
                ["git", "checkout", self.commit], check=True, cwd=self._working_dir
            )
            subprocess.run(
                ["git", "checkout", "-b", self._default_branch_name],
                check=True,
                cwd=self._working_dir,
            )

    @classmethod
    def _derive_uid_from_url(cls, url: str) -> str:
        if url.startswith("https://"):
            path = url[len("https://") :]
        elif url.startswith("git@"):
            path = url.split(":", 1)[-1]
        elif url.startswith("file://"):
            path = url[len("file://") :]
        else:
            path = url
        parts = re.split(r"[./\\]", path)
        parts = [p for p in parts if p and p not in {"github", "com", "git", "example"}]
        return ("_".join(parts)).lower().replace("-", "_")

    @classmethod
    def get_default_working_dir(cls) -> Path:
        return _default_working_dir
