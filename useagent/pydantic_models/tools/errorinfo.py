from pydantic.dataclasses import dataclass


@dataclass(kw_only=True, frozen=True)
class ToolErrorInfo:
    """
    Represents an error originated from a tool.
    This is different from a 'poor result'.
    """

    # DevNote:
    # Intially we tried to have a @handle_error decorator, but the decorators do not properly support the
    # Required Schema from Pydantic AI. So we would raise or receive errors related to the schema when using them.
    # So instead, tools just receive a new return value. We first thought about `str`,
    # While that is ok for tools, it can confuse / fault agents that have [str] as their return value.
    # By havign a seperate return type for errors, we avoid issues on confusing that would rely on model judgement.

    message: str
    tool: str

    other_info: str | None = None
    supplied_arguments: dict[str, str] | None = None
