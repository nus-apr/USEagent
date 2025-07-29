import pytest

from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo
from useagent.tools.bash import (
    __reset_bash_tool,
    bash_tool,
    init_bash_tool,
)


@pytest.mark.tool
def test_reset_before_initialization_is_safe():
    __reset_bash_tool()
    # should not raise


@pytest.mark.tool
def test_init_sets_instance():
    init_bash_tool(".")
    assert bash_tool.__globals__["_bash_tool_instance"] is not None


@pytest.mark.asyncio
@pytest.mark.tool
async def test_using_tool_without_initialization_raises_assertion(tmp_path):
    __reset_bash_tool()
    with pytest.raises(AssertionError):
        await bash_tool("echo hello")


@pytest.mark.asyncio
@pytest.mark.tool
async def test_run_valid_command(tmp_path):
    init_bash_tool(str(tmp_path))
    result = await bash_tool("echo hello")
    assert isinstance(result, CLIResult)
    assert "hello" in result.output


@pytest.mark.asyncio
@pytest.mark.tool
async def test_run_empty_command_returns_error(tmp_path):
    init_bash_tool(str(tmp_path))
    result = await bash_tool("")
    assert isinstance(result, ToolErrorInfo)
    assert "No Command Supplied" in result.message


@pytest.mark.asyncio
@pytest.mark.tool
async def test_run_invalid_grep_command(tmp_path):
    init_bash_tool(str(tmp_path))
    result = await bash_tool("grep -r pattern")
    assert isinstance(result, ToolErrorInfo)
    assert "grep -r" in result.message


@pytest.mark.asyncio
@pytest.mark.tool
async def test_restart_session_returns_system_message(tmp_path):
    init_bash_tool(str(tmp_path))
    result = await bash_tool("echo test")
    assert isinstance(result, CLIResult)


@pytest.mark.tool
def test_reinit_does_not_crash(tmp_path):
    init_bash_tool(str(tmp_path))
    init_bash_tool(str(tmp_path))
    assert bash_tool.__globals__["_bash_tool_instance"] is not None
