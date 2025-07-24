import pytest

from useagent.tools.bash import __reset_bash_tool


@pytest.fixture(autouse=True)
def reset_the_edit_tools():
    __reset_bash_tool()
    yield
    __reset_bash_tool()
