import pytest

from useagent.pydantic_models.common.constrained_types import (
    _strip_whitespace_except_for_trailing_newlines,
)


def test_plain_text_should_strip_spaces_tabs_not_newline():
    assert _strip_whitespace_except_for_trailing_newlines("  foo\t ") == "foo"


def test_trailing_newline_should_be_preserved_as_single_newline():
    assert _strip_whitespace_except_for_trailing_newlines("  foo  \n") == "foo\n"
    assert _strip_whitespace_except_for_trailing_newlines(" \tfoo\t \n\n") == "foo\n"


def test_no_trailing_newline_should_not_add_one():
    assert _strip_whitespace_except_for_trailing_newlines("foo  ") == "foo"


def test_only_whitespace_should_become_empty():
    assert _strip_whitespace_except_for_trailing_newlines("   \t ") == ""
    assert (
        _strip_whitespace_except_for_trailing_newlines("  \n\t  ") == ""
    )  # stripped core is empty → empty string


def test_internal_whitespace_should_be_untouched():
    assert _strip_whitespace_except_for_trailing_newlines(" a  b \n") == "a  b\n"


def test_crlf_should_result_in_single_newline():
    assert _strip_whitespace_except_for_trailing_newlines(" foo \r\n") == "foo\n"
    assert _strip_whitespace_except_for_trailing_newlines("foo\r\n\r\n") == "foo\n"


def test_no_mutation_when_already_clean():
    assert _strip_whitespace_except_for_trailing_newlines("bar\n") == "bar\n"
    assert _strip_whitespace_except_for_trailing_newlines("bar") == "bar"


def test_type_error_should_be_raised_for_non_str():
    with pytest.raises(TypeError):
        _strip_whitespace_except_for_trailing_newlines(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        _strip_whitespace_except_for_trailing_newlines(123)  # type: ignore[arg-type]
