import pytest

from useagent.config import ConfigSingleton
from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo
from useagent.tools.bash import (
    bash_tool,
    get_bash_history,
    init_bash_tool,
    make_bash_tool_for_agent,
)

# Wrap tool creation once per test using a fixed agent name
AGENT_NAME = "test-agent"


@pytest.fixture
def bash(tmp_path):
    init_bash_tool(str(tmp_path))
    return make_bash_tool_for_agent(AGENT_NAME)


@pytest.mark.asyncio
@pytest.mark.tool
async def test_run_valid_command_should_return_output(bash):
    result = await bash("echo hello")
    assert isinstance(result, CLIResult)
    assert "hello" in result.output


@pytest.mark.asyncio
@pytest.mark.tool
async def test_run_empty_command_should_return_error(bash):
    result = await bash("")
    assert isinstance(result, ToolErrorInfo)
    assert "No Command Supplied" in result.message


@pytest.mark.asyncio
@pytest.mark.tool
async def test_run_invalid_grep_command_should_not_have_special_outcome_unless_flag_set(
    tmp_path,
):
    init_bash_tool(str(tmp_path))
    result = await bash_tool("grep -r pattern")
    assert isinstance(result, CLIResult)


@pytest.mark.asyncio
@pytest.mark.tool
async def test_run_invalid_grep_command_should_have_special_outcome_with_optimization_toggle_on(
    tmp_path,
):
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["check-grep-command-arguments"] = True

    init_bash_tool(str(tmp_path))
    result = await bash_tool("grep -r pattern")
    assert isinstance(result, ToolErrorInfo)
    assert "grep -r" in result.message

    ConfigSingleton.reset()


@pytest.mark.asyncio
@pytest.mark.tool
async def test_restart_session_should_succeed(bash):
    result = await bash("echo test")
    assert isinstance(result, CLIResult)


@pytest.mark.asyncio
@pytest.mark.tool
async def test_pwd_should_return_correct_directory(bash, tmp_path):
    result = await bash("pwd")
    assert isinstance(result, CLIResult)
    assert result.output.strip() == str(tmp_path)


@pytest.mark.asyncio
@pytest.mark.tool
async def test_pwd_after_restart_should_return_correct_directory(bash, tmp_path):
    await bash("echo warmup")
    await bash("pwd")  # discard potential restart message
    result = await bash("pwd")
    assert result.output.strip() == str(tmp_path)


@pytest.mark.asyncio
@pytest.mark.tool
async def test_cd_and_pwd_should_report_new_directory(bash, tmp_path):
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    await bash(f"cd {subdir}")
    result = await bash("pwd")
    assert isinstance(result, CLIResult)
    assert result.output.strip() == str(subdir)


@pytest.mark.asyncio
@pytest.mark.tool
@pytest.mark.parametrize(
    "command",
    ["cd .", "true", "mkdir .", "touch dummyfile && rm dummyfile"],
)
async def test_commands_without_output_should_not_crash(bash, command):
    result = await bash(command)
    assert isinstance(result, CLIResult)


@pytest.mark.asyncio
@pytest.mark.tool
async def test_history_should_store_cli_result(bash):
    await bash("echo test")
    history = get_bash_history()
    assert len(history) == 1
    cmd, agent, result = history[0]
    assert cmd == "echo test"
    assert isinstance(result, CLIResult)


@pytest.mark.asyncio
@pytest.mark.tool
async def test_history_should_store_tool_error(bash):
    await bash("")
    history = get_bash_history()
    assert len(history) == 1
    assert isinstance(history[0][2], ToolErrorInfo)


@pytest.mark.asyncio
@pytest.mark.tool
async def test_history_should_reset_on_tool_reinit(tmp_path):
    init_bash_tool(str(tmp_path))
    tool = make_bash_tool_for_agent(AGENT_NAME)
    await tool("echo once")
    assert get_bash_history()
    init_bash_tool(str(tmp_path))
    assert get_bash_history() == []


@pytest.mark.asyncio
@pytest.mark.tool
async def test_agent_field_should_reflect_correct_value(bash):
    await bash("echo one")
    agent = get_bash_history()[0][1]
    assert agent == AGENT_NAME


@pytest.mark.asyncio
@pytest.mark.tool
async def test_agent_field_should_track_multiple_tools(tmp_path):
    init_bash_tool(str(tmp_path))
    tool1 = make_bash_tool_for_agent("AGENT1")
    tool2 = make_bash_tool_for_agent("AGENT2")
    await tool1("echo first")
    await tool2("echo second")
    history = get_bash_history()
    assert history[0][1] == "AGENT1"
    assert history[1][1] == "AGENT2"


@pytest.mark.asyncio
@pytest.mark.tool
async def test_agent_field_should_not_persist_after_reset(tmp_path):
    init_bash_tool(str(tmp_path))
    tool = make_bash_tool_for_agent("AGENT1")
    await tool("echo before")
    init_bash_tool(str(tmp_path))
    tool = make_bash_tool_for_agent("AGENT2")
    await tool("echo after")
    agent = get_bash_history()[0][1]
    assert agent == "AGENT2"
