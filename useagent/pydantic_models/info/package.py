from enum import Enum

from pydantic import field_validator
from pydantic.dataclasses import dataclass


class Source(str, Enum):
    SYSTEM = "system"
    PROJECT = "project"


@dataclass
class Package:
    name: str
    version: str
    source: Source

    @field_validator("version")
    @classmethod
    def check_version(cls, v: str) -> str:
        if not v[0].isdigit():
            raise ValueError("Version must start with a digit")
        return v
