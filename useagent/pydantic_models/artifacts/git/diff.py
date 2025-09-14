import re

from pydantic import computed_field, field_validator
from pydantic.dataclasses import dataclass

from useagent.common.patch_validation import _is_valid_patch
from useagent.pydantic_models.common.constrained_types import NonEmptyStr


@dataclass(frozen=True)
class DiffEntry:
    """
    Represents a `git diff` entry, of common types of git patches.

    Not all exotic variations are supported, see `validate_git_patch` and `_is_valid_patch`.
    Important: This is a `git diff`, not a (gnu) `diff`.
    """

    diff_content: NonEmptyStr

    @classmethod
    def get_output_instructions(cls) -> str:
        return """
        A `DiffEntry` contains two fields:

        1. `diff_content`: A string containing the code edits you made, in `unified diff` format.I should be able to use `git apply` directly with the content of this string to apply the edits again to the codebase.
        You are given a tool called `extract_diff`, which will generate a unified diff of the current changes in the codebase.
        You should use that tool after making all the sufficient changes, and then return the unified diff content as output.

        2. `notes`: Optional notes if you want to summarize what was done in this diff and what was the goal. This is optional, you can choose to omit it if you think there is nothing worth summarizing.
        """

    @computed_field(return_type=bool)
    def has_index(self) -> bool:
        return bool(
            re.search(
                r"^index\s+[0-9a-f]+\.\.[0-9a-f]+", self.diff_content, re.MULTILINE
            )
        )

    @computed_field(return_type=bool)
    def is_wrapped_in_code_blocks(self) -> bool:
        return self.diff_content.strip().startswith(
            "```"
        ) and self.diff_content.strip().endswith("```")

    @computed_field(return_type=int)
    def number_of_hunks(self) -> int:
        """
        Compute the number of hunks by lines that start with @@
        This is a simple heuristic but it should be fine.
        """
        return len(re.findall(r"^@@", self.diff_content, re.MULTILINE))

    @computed_field(return_type=bool)
    def has_no_newline_eof_marker(self) -> bool:
        return "\\ No newline at end of file" in self.diff_content

    @field_validator("diff_content")
    def validate_git_patch(cls, v: str) -> str:
        patch: str = v
        if not _is_valid_patch(patch):
            raise ValueError("Invalid git patch format")
        return v
