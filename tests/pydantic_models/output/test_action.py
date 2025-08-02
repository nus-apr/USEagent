import pytest

from useagent.pydantic_models.output.action import Action


@pytest.mark.pydantic_model
@pytest.mark.parametrize("bad_str", ["", " ", "\n", "\t"])
def test_constructor_should_raise_on_invalid_evidence(bad_str: str):
    with pytest.raises(ValueError):
        Action(success=True, evidence=bad_str, cli_output=[], errors=[], doubts="valid")


@pytest.mark.pydantic_model
@pytest.mark.parametrize("bad_str", ["", " ", "\n", "\t"])
def test_constructor_should_raise_on_invalid_doubts(bad_str: str):
    with pytest.raises(ValueError):
        Action(success=True, evidence="valid", cli_output=[], errors=[], doubts=bad_str)


@pytest.mark.pydantic_model
def test_constructor_should_allow_none_doubts():
    a = Action(success=True, evidence="valid", cli_output=[], errors=[], doubts=None)
    assert isinstance(a, Action)


@pytest.mark.pydantic_model
def test_get_output_instructions_should_not_return_none():
    assert Action.get_output_instructions() is not None
