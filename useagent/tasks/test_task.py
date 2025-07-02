from pathlib import Path
from useagent.tasks.task import Task

class TestTask(Task):
    def __init__(self, root: Path, issue_statement:str="Example Task"):
        self._root = root
        self._issue_statement = issue_statement

    def get_working_directory(self) -> Path:
        return self._root

    def get_issue_statement(self) -> str:
        return self._issue_statement
