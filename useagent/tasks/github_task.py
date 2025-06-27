import subprocess
from pathlib import Path
from loguru import logger
import re
import pytest
from useagent.tasks.task import Task
from useagent.state.git_repo import GitRepository


class GithubTask(Task):
    '''
    Task for cloning GitHub repositories into a working directory.
    '''
    repo_url: str = None
    issue_statement: str = None
    uid: str = None
    _working_dir: Path

    def __init__(self, issue_statement: str, repo_url: str, working_dir: Path = Path("/tmp/working_dir")):
        if not issue_statement or not issue_statement.strip():
            raise ValueError("issue_statement must be a non-empty string")
        if not repo_url or not repo_url.strip():
            raise ValueError("repo_url must be a non-empty string")
        if not (repo_url.startswith("https://") or repo_url.startswith("git@") or repo_url.startswith("file://")):
            raise ValueError("repo_url must be a valid SSH, HTTPS, or file Git URL")
        if not working_dir:
            raise ValueError("working_dir must be a valid Path instance")

        logger.info(f"[Setup] Setting up Github Task, cloning {repo_url} into {working_dir}")

        self.repo_url = repo_url
        self.issue_statement = issue_statement
        self._working_dir = working_dir
        self.uid = self._derive_uid_from_url(repo_url)
        self.clone_repo_to_working_dir()
        self.git_repo = GitRepository(local_path=self._working_dir)
        self.setup_project()

    def get_issue_statement(self) -> str:
        return self.issue_statement

    def get_working_directory(self) -> Path:
        return self._working_dir

    def clone_repo_to_working_dir(self) -> None:
        if self._working_dir.exists():
            subprocess.run(["rm", "-rf", str(self._working_dir)], check=True)
        subprocess.run(["git", "clone", self.repo_url, str(self._working_dir)], check=True)
    
    @classmethod
    def _derive_uid_from_url(cls, url: str) -> str:
        if url.startswith("https://"):
            path = url[len("https://"):]
        elif url.startswith("git@"):
            path = url.split(":", 1)[-1]
        elif url.startswith("file://"):
            path = url[len("file://"):]
        else:
            path = url
        parts = re.split(r'[./\\]', path)
        parts = [p for p in parts if p and p not in {"github", "com", "git", "example"}]
        return ('_'.join(parts)).lower().replace("-","_")
