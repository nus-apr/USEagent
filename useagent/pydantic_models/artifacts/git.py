import re
from dataclasses import field

from pydantic import computed_field, constr, field_validator, model_validator
from pydantic.dataclasses import dataclass

from useagent.pydantic_models.common.constrained_types import NonEmptyStr

DIFF_HEADER_RE = re.compile(r"^diff --git a/.+ b/.+", re.MULTILINE)
HUNK_RE = re.compile(r"^@@", re.MULTILINE)
FILE_HEADER_RE = re.compile(r"^(---|\+\+\+) ", re.MULTILINE)
MODE_CHANGE_RE = re.compile(r"^(old mode|new mode) \d{6}", re.MULTILINE)
CODE_BLOCK_RE_DIFF = re.compile(
    r"^```diff\s*\n(.*?)\n```$", re.DOTALL
)  # Case 1: We might have a ```diff . If we have that, it MUST be followed by a newline
CODE_BLOCK_RE_GENERIC = re.compile(
    r"^\s*```\s*\n?(.*?)\n?```\s*$", re.DOTALL
)  # Case 2: We might have a generic code block ```, but then it can be followed by diff from the diff content.

RENAME_RE = re.compile(r"^rename (from|to) ", re.MULTILINE)


def _is_valid_patch(content: str) -> bool:
    if not DIFF_HEADER_RE.search(content):
        raise ValueError("Missing or Malformed 'diff --git' header")

    # Short Cut: There are git diffs that only change permissions.
    if MODE_CHANGE_RE.search(content):
        return True
    # Short Cut: There are git diffs that only rename files.
    if RENAME_RE.search(content):
        return True

    if not HUNK_RE.search(content):
        raise ValueError(
            "Missing or malformed content changes: no hunk (line-level change) found"
        )

    return True


@dataclass(frozen=True)
class DiffEntry:
    """
    Represents a `git diff` entry, of common types of git patches.
    Might be wrapped in Codeblocks (```), represented by the field is_wrapped_in_code_blocks.

    Not all exotic variations are supported, see `validate_git_patch` .
    Important: This is a `git diff`, not a (gnu) `diff`.
    """

    diff_content: NonEmptyStr
    notes: NonEmptyStr | None = None

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
        patch: str
        if match := CODE_BLOCK_RE_DIFF.match(v.strip()):
            patch = match.group(1).strip()
        elif match := CODE_BLOCK_RE_GENERIC.match(v.strip()):
            patch = match.group(1).strip()
        else:
            patch = v.strip()
        patch = patch.strip(
            "\n"
        )  # normalize leading/trailing newlines. The Regex Matching sometimes can be tricky.
        if not _is_valid_patch(patch):
            raise ValueError("Invalid git patch format")
        return v


@dataclass
class DiffStore:
    id_to_diff: dict[NonEmptyStr, DiffEntry] = field(default_factory=dict)

    # DevNote:
    # While add_entry checks for duplication and assignes keys manually,
    # as a pydantic_dataclass the model might initiate (simple) DiffStores from somewhere else.
    # These can be good but should still follow the same standards, so we also have model validators.
    @model_validator(mode="after")  # pyright: ignore[reportArgumentType]
    def check_no_duplicate_content(self) -> "DiffStore":
        seen = set()
        for e in self.id_to_diff.values():
            norm = e.diff_content.strip()
            if norm in seen:
                raise ValueError("Duplicate diff contents detected in initialization")
            seen.add(norm)
        return self

    @model_validator(mode="after")  # pyright: ignore[reportArgumentType]
    def check_key_format(self) -> "DiffStore":
        for k in self.id_to_diff:
            if not k.startswith("diff_"):
                raise ValueError(f"Invalid key in DiffStore: {k}")
        return self

    @computed_field(return_type=dict[DiffEntry, NonEmptyStr])
    def diff_to_id(self) -> dict[str, str]:
        # Reverse lookup to id_to_diff
        return {e.diff_content.strip(): k for k, e in self.id_to_diff.items()}

    def add_entry(
        self, entry: DiffEntry
    ) -> constr(strip_whitespace=True, min_length=1):
        """
        Add an existing diff entry and return its ID.
        Raise a ValueError if a duplicate of the entry already exists.
        """
        norm = entry.diff_content.strip()
        if any(e.diff_content.strip() == norm for e in self.id_to_diff.values()):
            raise ValueError("Equivalent diff already exists.")
        new_id = f"diff_{len(self.id_to_diff)}"
        self.id_to_diff[new_id] = entry
        return new_id

    # DevNote:
    # I had a `pop entry` at some point here, but this will give us horrible problems with the numbering !
    # Because if we have diff_1..5 and we delete 3, should we continue with diff_6, or fill diff_3 again?
    # Either way having it here is complex, suggestion: Removing elements should be done as a meta_agent tool and just make a completely new DiffStore.

    def __len__(self) -> int:
        return len(self.id_to_diff)
