from enum import Enum

from pydantic import field_validator
from pydantic.dataclasses import dataclass

from useagent.pydantic_models.common.constrained_types import NonEmptyStr


class Source(str, Enum):
    SYSTEM = "system"
    PROJECT = "project"


@dataclass
class Package:
    name: NonEmptyStr
    version: NonEmptyStr
    source: Source

    @field_validator("version")
    @classmethod
    def check_version(cls, v: str) -> str:
        if not v[0].isdigit():
            raise ValueError("Version must start with a digit")
        return v
