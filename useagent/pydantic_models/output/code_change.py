from pydantic.dataclasses import dataclass

from useagent.pydantic_models.artifacts.git import DiffEntry
from useagent.pydantic_models.common.constrained_types import NonEmptyStr


@dataclass
class CodeChange:
    explanation: NonEmptyStr
    change: DiffEntry
    doubts: NonEmptyStr | None

    @classmethod
    def get_output_instructions(cls) -> str:
        return (
            """
        A CodeChange consists of the following fields: 

        - explanation (Non Empty String): Describe what you have done, why you consider the change sufficient and explain reasons that you have done to explore its validity.
        - change (DiffEntry): A git diff code change that you consider fit to solve the task you were given. 
        - doubts (Non Empty String, or None): Optionally, if you think there are any counter arguments to what you have done, or necessary steps missed, or other anomalies, present them here.

        """
            + DiffEntry.get_output_instructions()
        )  # Also add instructions from how the diff-entry looks like.
