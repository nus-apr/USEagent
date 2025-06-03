"""
Persistent state for task, which is shared between MetaAgent and actions.
"""

from dataclasses import dataclass, field

from app.state.git_repo import GitRepository
from app.tasks.usebench_task import UseBenchTask


@dataclass
class Location:
    rel_file_path: str
    abs_file_path: str
    # line numbers are 1-based
    start: int | None
    end: int | None


@dataclass
class DiffEntry:
    diff_content: str
    notes: str | None = None


@dataclass
class DiffStore:
    id_to_diff: dict[str, DiffEntry] = field(default_factory=dict)


@dataclass
class TaskState:
    # TODO: generalize to other types of tasks
    task: UseBenchTask
    git_repo: GitRepository

    code_locations: list[Location] = field(default_factory=list)
    test_locations: list[Location] = field(default_factory=list)

    diff_store: DiffStore = field(default_factory=DiffStore)

    # stores any additional knowledge to remember
    additional_knowledge: dict[str, str] = field(default_factory=dict)

    def to_model_repr(self) -> str:
        """Return a string representation of the task state."""
        res = ""
        res += f"Code Locations: {self.code_locations}\n"
        res += f"Test Locations: {self.test_locations}\n"
        res += f"Diff Store: {self.diff_store.id_to_diff}\n"

        res += f"Additional Knowledge: {self.additional_knowledge}\n"

        return res
