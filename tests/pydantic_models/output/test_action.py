import pytest

from useagent.pydantic_models.output.action import Action
from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo


@pytest.mark.pydantic_model
@pytest.mark.parametrize("bad_str", ["", " ", "\n", "\t"])
def test_constructor_should_raise_on_invalid_evidence(bad_str: str):
    with pytest.raises(ValueError):
        Action(success=True, evidence=bad_str, execution_artifact=None, doubts="valid")


@pytest.mark.pydantic_model
@pytest.mark.parametrize("bad_str", ["", " ", "\n", "\t"])
def test_constructor_should_raise_on_invalid_doubts(bad_str: str):
    with pytest.raises(ValueError):
        Action(success=True, evidence="valid", execution_artifact=None, doubts=bad_str)


@pytest.mark.pydantic_model
def test_constructor_should_allow_none_doubts():
    a = Action(success=True, evidence="valid", execution_artifact=None, doubts=None)
    assert isinstance(a, Action)


@pytest.mark.pydantic_model
def test_constructor_should_accept_cliresult():
    a = Action(
        success=True, evidence="valid", execution_artifact=CLIResult(output="ok")
    )
    assert isinstance(a, Action)


@pytest.mark.pydantic_model
def test_constructor_should_accept_toolerrorinfo():
    a = Action(
        success=True, evidence="valid", execution_artifact=ToolErrorInfo(message="fail")
    )
    assert isinstance(a, Action)


"""
# DevNote: This ... failed? I think Exception is not a valid type. Not sure, I had to strip it from Action Too.
@pytest.mark.pydantic_model
def test_constructor_should_accept_exception():
    a = Action(success=False, evidence="valid", execution_artifact=Exception("boom"))
    assert isinstance(a, Action)
"""


@pytest.mark.pydantic_model
def test_constructor_should_accept_none_execution_artifact():
    a = Action(success=True, evidence="valid", execution_artifact=None)
    assert isinstance(a, Action)


@pytest.mark.pydantic_model
def test_get_output_instructions_should_not_return_none():
    assert Action.get_output_instructions() is not None
