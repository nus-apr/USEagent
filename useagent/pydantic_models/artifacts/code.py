import os

from pydantic import field_validator, model_validator
from pydantic.dataclasses import dataclass

from useagent.pydantic_models.common.constrained_types import (
    NonEmptyStr,
    NonNegativeInt,
)


@dataclass(frozen=True)
class Location:
    rel_file_path: NonEmptyStr
    start_line: NonNegativeInt
    end_line: NonNegativeInt
    code_content: NonEmptyStr
    reason_why_relevant: NonEmptyStr

    @field_validator("start_line", "end_line")
    @classmethod
    def line_numbers_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("line numbers must be positive")
        return v

    @field_validator("rel_file_path")
    @classmethod
    def rel_file_path_must_be_relative(cls, v: str) -> str:
        if os.path.isabs(v):
            raise ValueError(
                f"rel_file_path must be a relative path, {v} is a absolute path"
            )
        return v

    @model_validator(mode="after")
    def check_line_range(self) -> "Location":
        if self.end_line < self.start_line:
            raise ValueError("end_line must be greater or equal than start_line")
        return self

    @classmethod
    def get_output_instructions(cls) -> str:
        return """
        A location contains the following fields:

        - rel_file_path (Path): Relative file path (to the project root) of the location.
        - start_line (Non-Negative Integer): Start line number of the relevant code region in the file. Must be 1-based (i.e. the first line in the file is line 1).
        - end_line (Non-Negative Integer): End line number of the relevant code region in the file.
        - code_content (Non-Empty String): The actual code content within start_line and end_line.
        - reason_why_relevant (Non-Empty String): Why do you think this location is relevant.

        You should specify start_line and end_line such that they contain all the relevant code.
        """
