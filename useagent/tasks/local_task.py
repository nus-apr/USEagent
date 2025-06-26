import subprocess

from pathlib import Path

from useagent.tasks.task import Task
from useagent.state.git_repo import GitRepository

class LocalTask(Task):
    project_path: str = None
    issue_statement: str = None 
    uid:str = "local"

    def __init__(self, issue_statement: str,  project_path: str):
        self.project_path = project_path
        self.issue_statement = issue_statement
        self.git_repo = GitRepository(local_path=project_path)
        self.setup_project()

    def get_issue_statement(self) -> str:
        return self.issue_statement

    def get_working_directory(self) -> Path:
        if isinstance(self.project_path, Path):
            return self.project_path
        elif  isinstance(self.project_path,str):
            return Path(self.project_path)
        else:
            raise ValueError(f"Issue converting {self.project_path} to Path")


    def setup_project(self) -> None:
        """
        Run any remaining steps to set up the project.

        Assume we are in a container with both the agent and the target project.
        """
        git_cmd = f"git config --global --add safe.directory {self.project_path}"
        subprocess.run(
            git_cmd,
            shell=True,
            check=True,
            cwd=self.project_path,
        )
        #TODO: USEBenchTask had a pip install here. We might not need this either. 
