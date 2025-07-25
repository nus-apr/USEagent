import re
from dataclasses import field

from pydantic import computed_field, constr, field_validator
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


@dataclass(config=dict(arbitrary_types_allowed=True))  # type: ignore
class DiffStore:
    id_to_diff: dict[NonEmptyStr, DiffEntry] = field(default_factory=dict)  # type: ignore[reportInvalidTypeForm]

    def add_entry(
        self, entry: DiffEntry
    ) -> constr(strip_whitespace=True, min_length=1):
        """Add an existing diff entry and return its ID."""
        diff_id = f"diff_{len(self.id_to_diff)}"
        self.id_to_diff[diff_id] = entry
        return diff_id

    def __len__(self) -> int:
        return len(self.id_to_diff)
