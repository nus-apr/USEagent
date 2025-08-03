# tests/tools/bash/test_view_command_history.py

import pytest

from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo
from useagent.tools.bash import bash_tool, init_bash_tool
from useagent.tools.meta import view_command_history


@pytest.fixture(autouse=True)
def reset_bash_tool(tmp_path):
    init_bash_tool(str(tmp_path))
    yield
    init_bash_tool(str(tmp_path))


@pytest.mark.asyncio
@pytest.mark.tool
async def test_history_should_be_empty_initially():
    assert view_command_history() == []


@pytest.mark.asyncio
@pytest.mark.tool
async def test_history_should_return_last_command():
    await bash_tool("echo single")
    history = view_command_history()
    assert len(history) == 1
    assert history[0][0] == "echo single"
    assert isinstance(history[0][2], CLIResult)


@pytest.mark.asyncio
@pytest.mark.tool
async def test_history_should_limit_to_requested_number():
    for i in range(10):
        await bash_tool(f"echo {i}")
    history = view_command_history(limit=3)
    assert len(history) == 3
    assert history[0][0] == "echo 7"
    assert history[1][0] == "echo 8"
    assert history[2][0] == "echo 9"


@pytest.mark.asyncio
@pytest.mark.tool
async def test_history_should_return_tool_error():
    await bash_tool("")
    history = view_command_history()
    assert len(history) == 1
    assert isinstance(history[0][2], ToolErrorInfo)
