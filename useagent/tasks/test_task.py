from pathlib import Path
from useagent.tasks.task import Task

class TestTask(Task):
    """
    This task is a `dummy` that has no checks, and functions as a Mock. 
    It is only used in Unit-Tests, but rests in the project modules if 
    someone needs to use it in their tests or dummy trials.
    """
    __test__ = False  # Prevent pytest from collecting this as a test class

    def __init__(self, root: Path, issue_statement:str="Example Task"):
        self._root = root
        self._issue_statement = issue_statement

    def get_working_directory(self) -> Path:
        return self._root

    def get_issue_statement(self) -> str:
        return self._issue_statement
