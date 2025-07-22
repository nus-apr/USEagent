from collections.abc import Callable
from typing import TypeVar

from typing_extensions import ParamSpec

P = ParamSpec("P")
R = TypeVar("R")


class ToolError(Exception):
    """Raised when a tool encounters an error."""

    pass


def handle_toolerrors_as_strs(func: Callable[P, R]) -> Callable[P, R | str]:
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R | str:
        try:
            return func(*args, **kwargs)
        except ToolError as e:
            return str(e)

    return wrapper
