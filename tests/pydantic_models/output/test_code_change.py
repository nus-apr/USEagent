import pytest

from useagent.pydantic_models.output.code_change import CodeChange


@pytest.fixture
def valid_diff_entry() -> str:
    return "diff_0"


@pytest.mark.parametrize("bad_str", ["", " ", "   ", "\n", "\t"])
@pytest.mark.pydantic_model
def test_constructor_should_raise_on_invalid_explanation(
    bad_str: str, valid_diff_entry: str
):
    with pytest.raises(ValueError):
        CodeChange(explanation=bad_str, diff_id=valid_diff_entry, doubts="valid")


@pytest.mark.parametrize("bad_str", ["", " ", "   ", "\n", "\t", "test", "_diff_0"])
@pytest.mark.pydantic_model
def test_constructor_should_raise_on_invalid_diffs(bad_str: str):
    with pytest.raises(ValueError):
        CodeChange(explanation="thinking", diff_id=bad_str, doubts="valid")


@pytest.mark.parametrize("bad_str", ["", " ", "   ", "\n", "\t"])
@pytest.mark.pydantic_model
def test_constructor_should_raise_on_invalid_doubts(
    bad_str: str, valid_diff_entry: str
):
    with pytest.raises(ValueError):
        CodeChange(explanation="valid", diff_id=valid_diff_entry, doubts=bad_str)


@pytest.mark.pydantic_model
def test_constructor_should_allow_none_doubts(valid_diff_entry: str):
    c = CodeChange(explanation="valid", diff_id=valid_diff_entry, doubts=None)
    assert isinstance(c, CodeChange)


@pytest.mark.pydantic_model
def test_constructor_should_allow_none_doubts_2(valid_diff_entry: str):
    c = CodeChange(explanation="valid", diff_id="diff_2", doubts="None")
    assert isinstance(c, CodeChange)


@pytest.mark.pydantic_model
def test_get_output_instructions_should_not_return_none():
    assert CodeChange.get_output_instructions() is not None
