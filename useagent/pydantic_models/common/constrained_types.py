from typing import Annotated

from pydantic import BeforeValidator, Field, conint


def _strip_whitespace_except_for_trailing_newlines(v: str) -> str:
    """
    Strip leading/trailing spaces and tabs, but preserve a single trailing newline
    if the original had one. If the whole string is whitespace, return empty.
    """
    # See: Issue #43 on this
    if not isinstance(v, str):
        raise TypeError("Expected str")

    # Full strip for empties, do not allow \n\n to be valid.
    if v.strip() == "":
        return ""
    has_newline = v.endswith("\n")
    s = v.strip()

    # Re-add exactly one newline if there was at least one at the end
    if has_newline:
        if not s.endswith("\n"):
            s += "\n"

    return s


NonEmptyStr = Annotated[
    str,
    BeforeValidator(_strip_whitespace_except_for_trailing_newlines),
    Field(min_length=1),
]

PositiveInt = conint(gt=0)  # strictly > 0
NonNegativeInt = conint(ge=0)  # ≥ 0
