from pydantic.dataclasses import dataclass

from useagent.pydantic_models.common.constrained_types import NonEmptyStr


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

    message: NonEmptyStr
    tool: NonEmptyStr

    other_info: NonEmptyStr | None = None
    supplied_arguments: dict[NonEmptyStr, NonEmptyStr] | None = None
