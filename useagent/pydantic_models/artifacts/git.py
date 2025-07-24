from dataclasses import field

from pydantic import constr
from pydantic.dataclasses import dataclass

from useagent.pydantic_models.common.constrained_types import NonEmptyStr


@dataclass(frozen=True)
class DiffEntry:
    diff_content: NonEmptyStr
    notes: NonEmptyStr | None = None


@dataclass(config=dict(arbitrary_types_allowed=True))  # type: ignore
class DiffStore:
    id_to_diff: dict[NonEmptyStr, DiffEntry] = field(default_factory=dict)  # type: ignore[reportInvalidTypeForm]

    def add_entry(
        self, entry: DiffEntry
    ) -> constr(strip_whitespace=True, min_length=1):
        """Add an existing diff entry and return its ID."""
        diff_id = f"diff_{len(self.id_to_diff)}"
        self.id_to_diff[diff_id] = entry
        return diff_id

    def __len__(self) -> int:
        return len(self.id_to_diff)
