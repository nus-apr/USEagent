import pytest

from useagent.tools.edit import __reset_project_dir


@pytest.fixture(autouse=True)
def reset_the_edit_tools():
    __reset_project_dir()
    yield
    __reset_project_dir()
