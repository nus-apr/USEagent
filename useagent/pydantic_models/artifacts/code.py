from pydantic.dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    rel_file_path: str
    start_line: int
    end_line: int
    code_content: str
    reason_why_relevant: str
