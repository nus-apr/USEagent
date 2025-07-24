import pytest
from pydantic import ValidationError

from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo


@pytest.mark.pydantic_model
def test_valid_tool_error_info():
    ToolErrorInfo(
        message="Something failed",
        tool="example_tool",
        other_info="details here",
        supplied_arguments={"arg1": "value1"},
    )


@pytest.mark.pydantic_model
@pytest.mark.parametrize("field", ["message", "tool"])
@pytest.mark.parametrize("value", ["", " ", "\n"])
def test_required_fields_invalid(field: str, value: str):
    kwargs = {"message": "msg", "tool": "tool"}
    kwargs[field] = value
    with pytest.raises(ValidationError):
        ToolErrorInfo(**kwargs)


@pytest.mark.pydantic_model
@pytest.mark.parametrize("value", ["", " ", "\n"])
def test_optional_other_info_invalid(value: str):
    with pytest.raises(ValidationError):
        ToolErrorInfo(message="msg", tool="tool", other_info=value)


@pytest.mark.pydantic_model
def test_optional_fields_can_be_none():
    ToolErrorInfo(message="msg", tool="tool", other_info=None, supplied_arguments=None)
