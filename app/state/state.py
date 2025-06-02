"""
Persistent state for task, which is shared between MetaAgent and actions.
"""

from dataclasses import dataclass, field

from app.state.git_repo import GitRepository


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
    git_repo: GitRepository

    code_locations: list[Location] = field(default_factory=list)
    test_locations: list[Location] = field(default_factory=list)

    diff_store: DiffStore = field(default_factory=DiffStore)

    # stores any additional knowledge to remember
    additional_knowledge: dict[str, str] = field(default_factory=dict)
