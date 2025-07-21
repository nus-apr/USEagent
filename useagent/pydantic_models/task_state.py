from pydantic import BaseModel, Field, PrivateAttr

from useagent.pydantic_models.code import Location
from useagent.pydantic_models.git import DiffStore
from useagent.state.git_repo import GitRepository
from useagent.tasks.task import Task


class TaskState(BaseModel):
    _task: Task = PrivateAttr()
    _git_repo: GitRepository = PrivateAttr()

    code_locations: list[Location] = Field(default_factory=list)
    test_locations: list[Location] = Field(default_factory=list)

    diff_store: DiffStore = Field(default_factory=DiffStore)

    # stores any additional knowledge to remember
    additional_knowledge: dict[str, str] = Field(default_factory=dict)

    def __init__(self, task: Task, git_repo: GitRepository, **data):
        super().__init__(**data)
        self._task = task
        self._git_repo = git_repo

    def to_model_repr(self) -> str:
        return (
            f"Code Locations: {self.code_locations}\n"
            f"Test Locations: {self.test_locations}\n"
            f"Diff Store: {self.diff_store.id_to_diff}\n"
            f"Additional Knowledge: {self.additional_knowledge}\n"
        )
