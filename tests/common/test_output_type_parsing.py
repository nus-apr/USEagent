from argparse import ArgumentTypeError

import pytest

from useagent.main import parse_output_type
from useagent.pydantic_models.output.action import Action
from useagent.pydantic_models.output.answer import Answer
from useagent.pydantic_models.output.code_change import CodeChange


@pytest.mark.parametrize(
    "input_str,expected_type",
    [
        ("answer", Answer),
        ("Answer", Answer),
        ("ANSWER", Answer),
        (" codechange ", CodeChange),
        ("\tAction\n", Action),
    ],
)
def test_parse_output_type_should_return_expected_class(
    input_str: str, expected_type: type
):
    result = parse_output_type(input_str)
    assert result is expected_type


@pytest.mark.parametrize("bad_input", ["", "\n", "invalid", " answers ", "123", None])
def test_parse_output_type_should_raise_on_invalid_input(bad_input: str):
    with pytest.raises(ArgumentTypeError):
        parse_output_type(bad_input)
