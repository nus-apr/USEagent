import pytest

from useagent.pydantic_models.artifacts.test_result import TestResult


@pytest.mark.pydantic_model
@pytest.mark.parametrize("bad_str", ["", " ", "\n", "\t"])
def test_constructor_should_raise_on_invalid_executed_test_command(bad_str: str):
    with pytest.raises(ValueError):
        TestResult(
            executed_test_command=bad_str,
            test_successful=True,
            rationale="valid",
            selected_test_output=None,
            doubts=None,
        )


@pytest.mark.pydantic_model
@pytest.mark.parametrize("bad_str", ["", " ", "\n", "\t"])
def test_constructor_should_raise_on_invalid_rationale(bad_str: str):
    with pytest.raises(ValueError):
        TestResult(
            executed_test_command="valid",
            test_successful=True,
            rationale=bad_str,
            selected_test_output=None,
            doubts=None,
        )


@pytest.mark.pydantic_model
@pytest.mark.parametrize("bad_str", ["", " ", "\n", "\t"])
def test_constructor_should_raise_on_invalid_selected_test_output(bad_str: str):
    with pytest.raises(ValueError):
        TestResult(
            executed_test_command="valid",
            test_successful=True,
            rationale="valid",
            selected_test_output=bad_str,
            doubts=None,
        )


@pytest.mark.pydantic_model
@pytest.mark.parametrize("bad_str", ["", " ", "\n", "\t"])
def test_constructor_should_raise_on_invalid_doubts(bad_str: str):
    with pytest.raises(ValueError):
        TestResult(
            executed_test_command="valid",
            test_successful=True,
            rationale="valid",
            selected_test_output=None,
            doubts=bad_str,
        )


@pytest.mark.pydantic_model
def test_constructor_should_allow_valid_optional_fields():
    result = TestResult(
        executed_test_command="valid",
        test_successful=False,
        rationale="valid rationale",
        selected_test_output=None,
        doubts=None,
    )
    assert isinstance(result, TestResult)


@pytest.mark.pydantic_model
def test_get_output_instructions_should_not_return_none():
    assert TestResult.get_output_instructions() is not None
