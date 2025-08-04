import pytest

from useagent.pydantic_models.output.answer import Answer


@pytest.mark.parametrize("bad_str", ["", " ", "\n", "\t"])
@pytest.mark.pydantic_model
def test_constructor_should_raise_on_invalid_answer(bad_str: str):
    with pytest.raises(ValueError):
        Answer(answer=bad_str, explanation="valid", doubts="valid", environment=None)


@pytest.mark.parametrize("bad_str", ["", " ", "\n", "\t"])
@pytest.mark.pydantic_model
def test_constructor_should_raise_on_invalid_explanation(bad_str: str):
    with pytest.raises(ValueError):
        Answer(answer="valid", explanation=bad_str, doubts="valid", environment=None)


@pytest.mark.parametrize("bad_str", ["", " ", "\n", "\t"])
@pytest.mark.pydantic_model
def test_constructor_should_raise_on_invalid_doubts(bad_str: str):
    with pytest.raises(ValueError):
        Answer(answer="valid", explanation="valid", doubts=bad_str, environment=None)


@pytest.mark.pydantic_model
def test_constructor_should_allow_none_doubts():
    a = Answer(answer="valid", explanation="valid", doubts=None, environment=None)
    assert isinstance(a, Answer)


@pytest.mark.pydantic_model
def test_constructor_should_allow_none_environment():
    a = Answer(answer="valid", explanation="valid", doubts=None, environment=None)
    assert isinstance(a, Answer)


@pytest.mark.pydantic_model
def test_get_output_instructions_should_not_return_none():
    assert Answer.get_output_instructions() is not None
