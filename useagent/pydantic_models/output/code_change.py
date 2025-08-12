from pydantic import field_validator
from pydantic.dataclasses import dataclass

from useagent.pydantic_models.common.constrained_types import NonEmptyStr


@dataclass
class CodeChange:
    explanation: NonEmptyStr
    # DevNote:
    # Initially we had a DiffEntry here, but it was very hard for the Meta-Agent to formulate this dataclass then.
    # We now use the diff_id and resolve it later.
    diff_id: NonEmptyStr
    doubts: NonEmptyStr | None

    @field_validator("diff_id")
    def check_diff_id_format(cls, v: str) -> str:
        if not v.startswith("diff_"):
            raise ValueError(f"Invalid diff_id: {v}. Must start with diff_")
        return v

    @classmethod
    def get_output_instructions(cls) -> str:
        return """
        A CodeChange consists of the following fields: 

        - explanation (Non Empty String): Describe what you have done, why you consider the change sufficient and explain reasons that you have done to explore its validity.
        - diff_id (Non Empty String): the diff_id to identify a git diff code change that you consider fit to solve the task you were given. Should match a pattern of diff_0, diff_1, ... as present in your diff-store. 
        - doubts (Non Empty String, or None): Optionally, if you think there are any counter arguments to what you have done, or necessary steps missed, or other anomalies, present them here. Keep this based on facts, and do not raise generic doubts.

        """
