import re

# Mapping ProxyType is the 'read only' version of a Mapping (dict) because pydantic does not have a frozendict.
from collections.abc import Mapping
from dataclasses import field
from types import MappingProxyType
from typing import Annotated

from pydantic import BeforeValidator, ConfigDict, Field, computed_field, model_validator
from pydantic.dataclasses import dataclass

from useagent.pydantic_models.artifacts.git.diff import DiffEntry


def _normalize_diff_key(v: str) -> str:
    if not isinstance(v, str):
        raise TypeError("Expected str")
    v = v.strip().lower()
    if not re.fullmatch(r"diff_\d+", v):
        raise ValueError("DiffEntryKey must match 'diff_<nonnegative int>'")
    return v


DiffEntryKey = Annotated[
    str,
    BeforeValidator(_normalize_diff_key),
    Field(pattern=r"^diff_\d+$"),
]


@dataclass(config=ConfigDict(revalidate_instances="always"))
class DiffStore:
    _id_to_diff: dict[DiffEntryKey, DiffEntry] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self._id_to_diff:
            raise ValueError("DiffStore must be initialized empty")

    @model_validator(mode="after")  # pyright: ignore[reportArgumentType]
    def check_no_duplicate_content(self) -> "DiffStore":
        seen = set()
        for e in self._id_to_diff.values():
            norm = e.diff_content.strip()
            if norm in seen:
                raise ValueError("Duplicate diff contents detected in initialization")
            seen.add(norm)
        return self

    @model_validator(mode="after")  # pyright: ignore[reportArgumentType]
    def check_key_format(self) -> "DiffStore":
        for k in self._id_to_diff:
            if not k.startswith("diff_"):
                raise ValueError(f"Invalid key in DiffStore: {k}")
        return self

    # PUBLIC READ-ONLY VIEWS
    @computed_field(return_type=Mapping[DiffEntryKey, DiffEntry])
    def id_to_diff(self) -> Mapping[DiffEntryKey, DiffEntry]:
        # live, immutable view over the private dict
        return MappingProxyType(self._id_to_diff)

    @computed_field(return_type=Mapping[str, DiffEntryKey])
    def diff_to_id(self) -> Mapping[str, DiffEntryKey]:
        # snapshot of reverse mapping, also immutable
        reverse = {e.diff_content: k for k, e in self._id_to_diff.items()}
        return MappingProxyType(reverse)

    # PRIVATE WRITE PATH
    def _add_entry(self, entry: DiffEntry) -> DiffEntryKey:
        norm = entry.diff_content.strip()
        if any(e.diff_content.strip() == norm for e in self._id_to_diff.values()):
            raise ValueError("Equivalent diff already exists.")
        new_id = f"diff_{len(self._id_to_diff)}"
        self._id_to_diff[new_id] = entry
        return new_id

    def __len__(self) -> int:
        return len(self._id_to_diff)
