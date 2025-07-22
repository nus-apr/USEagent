from typing import Union, get_args, get_origin

import pytest

from useagent.tools.common.toolerror import ToolError, handle_toolerrors_as_strs


@handle_toolerrors_as_strs
def returns_true() -> bool:
    return True


@handle_toolerrors_as_strs
def raises_toolerror() -> bool:
    raise ToolError("tool failed")


@handle_toolerrors_as_strs
def adds(a: int, b: int) -> int:
    return a + b


@handle_toolerrors_as_strs
def fails_add(a: int, b: int) -> int:
    raise ToolError("bad add")


@handle_toolerrors_as_strs
def returns_nothing() -> None:
    pass


@handle_toolerrors_as_strs
def raises_value_error() -> str:
    raise ValueError("other failure")


def test_returns_true():
    assert returns_true() is True


def test_raises_toolerror():
    assert raises_toolerror() == "tool failed"


def test_adds():
    assert adds(2, 3) == 5


def test_fails_add():
    assert fails_add(1, 2) == "bad add"


def test_returns_nothing():
    assert returns_nothing() is None


def test_raises_value_error():
    with pytest.raises(ValueError):
        raises_value_error()


def test_return_type_returns_true():
    ret = returns_true.__annotations__["return"]
    assert get_origin(ret) is Union
    assert str in get_args(ret)


def test_return_type_raises_toolerror():
    ret = raises_toolerror.__annotations__["return"]
    assert get_origin(ret) is Union
    assert str in get_args(ret)


def test_return_type_adds():
    ret = adds.__annotations__["return"]
    assert get_origin(ret) is Union
    assert str in get_args(ret)


def test_return_type_fails_add():
    ret = fails_add.__annotations__["return"]
    assert get_origin(ret) is Union
    assert str in get_args(ret)


def test_return_type_returns_nothing():
    ret = returns_nothing.__annotations__["return"]
    assert get_origin(ret) is Union
    assert str in get_args(ret)


def test_return_type_raises_value_error():
    ret = raises_value_error.__annotations__["return"]
    assert get_origin(ret) is Union
    assert str in get_args(ret)
