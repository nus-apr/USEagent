import pytest

from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo
from useagent.tools.bash import (
    bash_tool,
    get_bash_history,
    init_bash_tool,
    set_current_running_agent,
)


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


@pytest.mark.asyncio
@pytest.mark.tool
async def test_pwd_returns_correct_directory(tmp_path):
    init_bash_tool(str(tmp_path))
    result = await bash_tool("pwd")
    assert isinstance(result, CLIResult)
    assert result.output.strip() == str(tmp_path)


@pytest.mark.asyncio
@pytest.mark.tool
async def test_pwd_after_restart_returns_correct_directory(tmp_path):
    init_bash_tool(str(tmp_path))
    await bash_tool("echo warmup")
    result = await bash_tool("pwd")
    assert isinstance(result, CLIResult)
    # skip the "tool has been restarted" result
    result = await bash_tool("pwd")
    assert result.output.strip() == str(tmp_path)


@pytest.mark.asyncio
@pytest.mark.tool
async def test_cd_and_pwd_reports_new_directory(tmp_path):
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    init_bash_tool(str(tmp_path))

    await bash_tool(f"cd {subdir}")
    result = await bash_tool("pwd")
    assert isinstance(result, CLIResult)
    assert result.output.strip() == str(subdir)


@pytest.mark.asyncio
@pytest.mark.tool
@pytest.mark.parametrize(
    "command",
    [
        "cd .",
        "true",
        "mkdir .",
        "touch dummyfile && rm dummyfile",
    ],
)
async def test_commands_without_output_do_not_crash(tmp_path, command):
    # DevNote: After introducing a check that each CLI must have either a output, or an error,
    # A simple `cd` did not work, because it prints nothing.
    init_bash_tool(str(tmp_path))
    result = await bash_tool(command)
    assert isinstance(result, CLIResult)


@pytest.mark.asyncio
@pytest.mark.tool
async def test_history_should_store_cli_result(tmp_path):
    init_bash_tool(str(tmp_path))
    await bash_tool("echo test")
    history = get_bash_history()
    assert len(history) == 1
    cmd, wd, result = history[0]
    assert cmd == "echo test"
    assert isinstance(result, CLIResult)


@pytest.mark.asyncio
@pytest.mark.tool
async def test_history_should_store_tool_error(tmp_path):
    init_bash_tool(str(tmp_path))
    await bash_tool("")
    history = get_bash_history()
    assert len(history) == 1
    assert isinstance(history[0][2], ToolErrorInfo)


@pytest.mark.asyncio
@pytest.mark.tool
async def test_history_should_reset_on_tool_reinit(tmp_path):
    init_bash_tool(str(tmp_path))
    await bash_tool("echo once")
    assert get_bash_history()
    init_bash_tool(str(tmp_path))
    assert get_bash_history() == []


@pytest.mark.asyncio
@pytest.mark.tool
async def test_agent_field_should_not_be_none_by_default(tmp_path):
    init_bash_tool(str(tmp_path))
    await bash_tool("echo one")
    agent = get_bash_history()[0][1]
    assert agent is not None


@pytest.mark.asyncio
@pytest.mark.tool
async def test_agent_field_should_reflect_test(tmp_path):
    init_bash_tool(str(tmp_path))
    set_current_running_agent("TEST")
    await bash_tool("echo test")
    assert get_bash_history()[0][1] == "TEST"


@pytest.mark.asyncio
@pytest.mark.tool
async def test_agent_field_should_reflect_last_set_value(tmp_path):
    init_bash_tool(str(tmp_path))
    set_current_running_agent("TEST")
    set_current_running_agent("FOO")
    await bash_tool("echo test")
    assert get_bash_history()[0][1] == "FOO"


@pytest.mark.asyncio
@pytest.mark.tool
async def test_agent_field_should_track_multiple_set_values(tmp_path):
    init_bash_tool(str(tmp_path))
    set_current_running_agent("TEST")
    await bash_tool("echo first")
    set_current_running_agent("FOO")
    await bash_tool("echo second")
    history = get_bash_history()
    assert history[0][1] == "TEST"
    assert history[1][1] == "FOO"


@pytest.mark.asyncio
@pytest.mark.tool
async def test_agent_field_should_not_persist_across_reset(tmp_path):
    init_bash_tool(str(tmp_path))
    set_current_running_agent("TEST")
    await bash_tool("echo before")
    init_bash_tool(str(tmp_path))
    await bash_tool("echo after")
    agent = get_bash_history()[0][1]
    assert agent is not None and agent != "TEST"
