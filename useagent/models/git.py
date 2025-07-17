
from dataclasses import field
from pydantic.dataclasses import dataclass

from typing import Dict

@dataclass(frozen=True)
class DiffEntry:
    diff_content: str
    notes: str | None = None


@dataclass(config=dict(arbitrary_types_allowed=True))
class DiffStore:
    id_to_diff: Dict[str, DiffEntry] = field(default_factory=dict)

    def add_entry(self, entry: DiffEntry) -> str:
        """Add an existing diff entry and return its ID."""
        diff_id = f"diff_{len(self.id_to_diff)}"
        self.id_to_diff[diff_id] = entry
        return diff_id

    def __len__(self) -> int:
        return len(self.id_to_diff)
