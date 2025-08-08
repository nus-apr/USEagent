from pydantic import field_validator
from pydantic.dataclasses import dataclass

from useagent.pydantic_models.common.constrained_types import NonEmptyStr


@dataclass
class Package:
    name: NonEmptyStr
    version: NonEmptyStr
    source: NonEmptyStr

    @field_validator("version")
    @classmethod
    def check_version(cls, v: str) -> str:
        if not v[0].isdigit() and not v[0].lower() == "v":
            raise ValueError("Version must start with a digit or with `v`")
        return v

    @classmethod
    def get_output_instructions(cls) -> str:
        return """
        A `Package` consists of:

        - `name`: `str`, the name of the package.
        - `version`: `str`, the currently installed version.
        - `source`: `str`, whether it's a system-level (e.g. apt) or project-level (e.g. pip, mvn) package.
        """
