from pathlib import Path

import pytest

from useagent.config import ConfigSingleton
from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo
from useagent.tools.bash import (
    bash_tool,
    init_bash_tool,
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
async def test_restart_session_returns_system_message(tmp_path: Path):
    init_bash_tool(str(tmp_path))
    result = await bash_tool("echo test")
    assert isinstance(result, CLIResult)


@pytest.mark.asyncio
@pytest.mark.tool
async def test_pwd_returns_correct_directory(tmp_path: Path):
    init_bash_tool(str(tmp_path))
    result = await bash_tool("pwd")
    assert isinstance(result, CLIResult)
    assert result.output.strip() == str(tmp_path)


@pytest.mark.asyncio
@pytest.mark.tool
async def test_pwd_after_restart_returns_correct_directory(tmp_path: Path):
    init_bash_tool(str(tmp_path))
    await bash_tool("echo warmup")
    result = await bash_tool("pwd")
    assert isinstance(result, CLIResult)
    # skip the "tool has been restarted" result
    result = await bash_tool("pwd")
    assert result.output.strip() == str(tmp_path)


@pytest.mark.asyncio
@pytest.mark.tool
async def test_cd_and_pwd_reports_new_directory(tmp_path: Path):
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
async def test_commands_without_output_do_not_crash(tmp_path: Path, command):
    # DevNote: After introducing a check that each CLI must have either a output, or an error,
    # A simple `cd` did not work, because it prints nothing.
    init_bash_tool(str(tmp_path))
    result = await bash_tool(command)
    assert isinstance(result, CLIResult)


@pytest.mark.slow
@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_bash_tool_large_output_should_be_shortened(tmp_path: Path, monkeypatch):
    # Issue #30 - long outputs should be shorted
    ConfigSingleton.reset()

    init_bash_tool(str(tmp_path))
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    ConfigSingleton.init("google-gla:gemini-2.5-flash")
    ConfigSingleton.config.context_window_limits["google-gla:gemini-2.5-flash"] = 80

    command = 'yes "This is a long line of output" | head -n 100'
    result = await bash_tool(command)
    assert isinstance(result, CLIResult)
    assert "[[ ... Cut to fit Context Window ... ]]" in result.output

    ConfigSingleton.reset()


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_bash_tool_short_output_should_not_be_shortened(
    tmp_path: Path, monkeypatch
):
    # Issue #30 - short outputs are fine
    ConfigSingleton.reset()

    init_bash_tool(str(tmp_path))
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    ConfigSingleton.init("google-gla:gemini-2.5-flash")
    ConfigSingleton.config.context_window_limits["google-gla:gemini-2.5-flash"] = 25000

    command = 'yes "This is a long line of output" | head -n 10'
    result = await bash_tool(command)
    assert isinstance(result, CLIResult)
    assert "[[ ... Cut to fit Context Window ... ]]" not in result.output

    ConfigSingleton.reset()
