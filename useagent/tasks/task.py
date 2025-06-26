from pathlib import Path
from useagent.state.git_repo import GitRepository


class Task:
    '''
    Base Class for all Tasks, providing default 

    For now, we require all Tasks to be Git Related.
    '''

    git_repo: GitRepository

    def setup_project(self):
        raise NotImplementedError("Subclasses need to implement this")

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