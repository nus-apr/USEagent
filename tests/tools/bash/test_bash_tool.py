import json
import time
from pathlib import Path

import pytest

from useagent.config import ConfigSingleton
from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo
from useagent.tools.bash import (
    __reset_bash_tool,
    bash_tool,
    get_bash_history,
    init_bash_tool,
    make_bash_tool_for_agent,
)

# Wrap tool creation once per test using a fixed agent name
AGENT_NAME = "test-agent"


@pytest.fixture(autouse=True)
def reset_config_and_bash_tool_each_test():
    __reset_bash_tool()
    ConfigSingleton.reset()
    yield
    __reset_bash_tool()
    ConfigSingleton.reset()


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
async def test_cd_and_pwd_should_report_new_directory(bash, tmp_path):
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    await bash(f"cd {subdir}")
    result = await bash("pwd")
    assert isinstance(result, CLIResult)
    assert result.output.strip() == str(subdir)


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


@pytest.mark.asyncio
@pytest.mark.tool
@pytest.mark.time_sensitive
async def test_bash_tool_should_wait_at_least_delay_seconds(tmp_path):
    init_bash_tool(str(tmp_path))
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["bash-tool-speed-bumper"] = True

    delay = 1.2
    start = time.monotonic()

    test_bash_tool = make_bash_tool_for_agent(bash_call_delay_in_seconds=delay)

    result = await test_bash_tool("echo timing")
    duration = time.monotonic() - start

    assert isinstance(result, CLIResult)
    assert duration >= delay


@pytest.mark.asyncio
@pytest.mark.tool
@pytest.mark.time_sensitive
async def test_bash_tool_should_not_wait_when_speed_bumper_disabled(tmp_path):
    init_bash_tool(str(tmp_path))
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["bash-tool-speed-bumper"] = False

    delay = 1.2
    start = time.monotonic()

    test_bash_tool = make_bash_tool_for_agent(bash_call_delay_in_seconds=delay)
    result = await test_bash_tool("echo quick")

    duration = time.monotonic() - start
    assert isinstance(result, CLIResult)
    assert duration < 1.0  # allow slight overhead


@pytest.mark.asyncio
@pytest.mark.tool
@pytest.mark.time_sensitive
async def test_bash_tool_should_not_wait_when_delay_is_zero(tmp_path):
    init_bash_tool(str(tmp_path))
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["bash-tool-speed-bumper"] = True

    start = time.monotonic()

    test_bash_tool = make_bash_tool_for_agent(bash_call_delay_in_seconds=0.0)
    result = await test_bash_tool("echo zero")

    duration = time.monotonic() - start
    assert isinstance(result, CLIResult)
    assert duration < 1.0


@pytest.mark.asyncio
@pytest.mark.tool
@pytest.mark.time_sensitive
async def test_bash_tool_should_not_wait_when_delay_is_negative(tmp_path):
    init_bash_tool(str(tmp_path))
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["bash-tool-speed-bumper"] = True

    start = time.monotonic()

    test_bash_tool = make_bash_tool_for_agent(bash_call_delay_in_seconds=-2.0)
    result = await test_bash_tool("echo negative")

    duration = time.monotonic() - start
    assert isinstance(result, CLIResult)
    assert duration < 1.0


@pytest.mark.asyncio
@pytest.mark.tool
@pytest.mark.time_sensitive
async def test_bash_tool_should_wait_for_3_seconds_if_set(tmp_path):
    init_bash_tool(str(tmp_path))
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["bash-tool-speed-bumper"] = True

    delay = 3.0
    start = time.monotonic()

    test_bash_tool = make_bash_tool_for_agent(bash_call_delay_in_seconds=delay)
    result = await test_bash_tool("echo longdelay")

    duration = time.monotonic() - start
    assert isinstance(result, CLIResult)
    assert duration >= delay


@pytest.mark.asyncio
@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.time_sensitive
async def test_bash_tool_can_cause_a_timeout(tmp_path):
    # See Issue 19 on this matter
    init_bash_tool(str(tmp_path))
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["bash-tool-speed-bumper"] = True

    test_bash_tool = make_bash_tool_for_agent(bash_call_delay_in_seconds=0.1)
    result = await test_bash_tool("echo hello")

    import useagent.tools.bash as bash_file

    _bash_tool_instance = bash_file._bash_tool_instance
    assert _bash_tool_instance

    assert not _bash_tool_instance._session._timed_out
    _bash_tool_instance._session._timeout = 1

    result = await test_bash_tool("sleep 2")

    assert isinstance(result, ToolErrorInfo)
    assert "time" in result.message
    assert _bash_tool_instance._session._timed_out


@pytest.mark.asyncio
@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.time_sensitive
async def test_bash_tool_can_cause_a_timeout_but_will_recover(tmp_path):
    # See Issue 19 on this matter
    init_bash_tool(str(tmp_path))
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["bash-tool-speed-bumper"] = True

    test_bash_tool = make_bash_tool_for_agent(bash_call_delay_in_seconds=0.1)
    # This will just pass
    await test_bash_tool("echo hello")

    import useagent.tools.bash as bash_file

    _bash_tool_instance = bash_file._bash_tool_instance
    assert _bash_tool_instance
    _bash_tool_instance._session._timeout = 1.0

    # This will Error / Timeout
    await test_bash_tool("sleep 2")

    # This should pass again, as the shell ought to be restarted
    result = await test_bash_tool("echo hello")
    assert result and isinstance(result, CLIResult)
    assert not _bash_tool_instance._session._timed_out


@pytest.mark.asyncio
@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.time_sensitive
async def test_bash_tool_default_directory_after_restart(tmp_path):
    # See Issue 19 on this matter
    # Particularly there was a follow up issue that it would set it to the projects source (i.e. /useagent in the containers), which messed up things quite badly.
    init_bash_tool(str(tmp_path))
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["bash-tool-speed-bumper"] = True

    test_bash_tool = make_bash_tool_for_agent(bash_call_delay_in_seconds=0.1)
    # This will just pass
    await test_bash_tool("echo hello")

    import useagent.tools.bash as bash_file

    _bash_tool_instance = bash_file._bash_tool_instance
    assert _bash_tool_instance
    _bash_tool_instance._session._timeout = 1.0

    # This will Error / Timeout
    await test_bash_tool("sleep 2")

    # This should pass again, as the shell ought to be restarted
    result = await test_bash_tool("pwd")
    assert result and isinstance(result, CLIResult)
    assert not _bash_tool_instance._session._timed_out
    assert "useagent" not in result.output.lower()


@pytest.mark.asyncio
@pytest.mark.tool
@pytest.mark.parametrize(
    "command",
    ["cd .", "true", "mkdir .", "touch dummyfile && rm dummyfile"],
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


@pytest.mark.time_sensitive
@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_bash_tool_command_with_eof_sign_should_not_timeout(
    tmp_path: Path, monkeypatch
):
    # Issue #29 - We have seen some strange behaviour with nested commands that need EOF
    init_bash_tool(str(tmp_path))

    test_bash_tool = make_bash_tool_for_agent(bash_call_delay_in_seconds=0.1)
    # This will just pass
    await test_bash_tool("echo hello")

    import useagent.tools.bash as bash_file

    _bash_tool_instance = bash_file._bash_tool_instance
    assert _bash_tool_instance
    _bash_tool_instance._session._timeout = 1.0

    command = """
/opt/venv/bin/python - <<'PY'
import importlib.metadata as m, json
pkgs = ["pytest","click","httpx","httpcore","openai","uvicorn","attrs","aiohttp","python-dotenv","coverage","jinja2","werkzeug","flit_core","tox","mypy","ruff","pre_commit"]
out={}
for p in pkgs:
  try:
    out[p]=m.version(p)
  except Exception as e:
    out[p]=None
print(json.dumps(out))
PY
    """
    result = await test_bash_tool(command)
    assert isinstance(result, CLIResult)
    # DevNote: These do have a result.error, because the syntax is not handled well. But not the observed issue in the experiments


@pytest.mark.time_sensitive
@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_bash_tool_command_with_eof_sign_should_not_timeout_example_other_command_with_apt_packages(
    tmp_path: Path, monkeypatch
):
    # Issue #29 - We have seen some strange behaviour with nested commands that need EOF
    init_bash_tool(str(tmp_path))

    test_bash_tool = make_bash_tool_for_agent(bash_call_delay_in_seconds=0.1)
    # This will just pass
    await test_bash_tool("echo hello")

    import useagent.tools.bash as bash_file

    _bash_tool_instance = bash_file._bash_tool_instance
    assert _bash_tool_instance
    _bash_tool_instance._session._timeout = 1.0

    command = "set -e; echo 'Checking common tools...'; for cmd in node npm npx yarn bun php composer python3 pip3 java mvn go cargo dotnet docker podman rpm dpkg apk apk --version 2>/dev/null || true; do :; done; \n# Print versions if commands exist\nfor c in node npm npx yarn bun php composer python3 pip3 java mvn go cargo dotnet docker podman dpkg rpm apk; do\n  if command -v \"$c\" >/dev/null 2>&1; then\n    if [ \"$c\" = \"java\" ]; then\n      echo \"$c: $(java -version 2>&1 | sed -n '1p')\"\n    else\n      ver=$($c --version 2>&1 || $c -v 2>&1 || true)\n      echo \"$c: ${ver%%$'\\n'*}\"\n    fi\n  else\n    echo \"$c: not found\"\n  fi\ndone\n\n# Node global packages (if npm exists)\nif command -v npm >/dev/null 2>&1; then\n  echo '--- npm global packages (top 40 lines) ---'\n  npm ls -g --depth=0 2>/dev/null | sed -n '1,200p'\nfi\n\n# pip3 list top\nif command -v pip3 >/dev/null 2>&1; then\n  echo '--- pip3 packages (top 80 lines) ---'\n  pip3 list --format=columns 2>/dev/null | sed -n '1,200p'\nfi\n\n# composer version\nif command -v composer >/dev/null 2>&1; then\n  composer --version\nfi\n\n# Show package.json dependencies summary\necho '--- package.json dependencies summary ---'\nnode -e \"const fs=require('fs');const p=JSON.parse(fs.readFileSync('package.json')); console.log('name:'+p.name+'@'+p.version); console.log('dependencies:'+Object.keys(p.dependencies||{}).slice(0,50).join(',')); console.log('devDependencies:'+Object.keys(p.devDependencies||{}).slice(0,200).join(','));\" 2>/dev/null || true\n\n# Show composer.json name\nif [ -f composer.json ]; then\n  jq -r '.name + \"@\" + (.version // \"\")' composer.json 2>/dev/null || sed -n '1,60p' composer.json | sed -n '1,2p'\nfi\n\n# Print python version\nif command -v python3 >/dev/null 2>&1; then python3 --version; fi\n\n# end"
    result = await test_bash_tool(command)
    assert isinstance(result, CLIResult)
    # DevNote: These do have a result.error, because the syntax is not handled well. But not the observed issue


@pytest.mark.asyncio
@pytest.mark.regression
@pytest.mark.tool
async def test_restart_bash_session_using_config_directory_should_start_in_config_dir(
    tmp_path: Path, monkeypatch
):
    init_bash_tool(str(tmp_path))
    tool = make_bash_tool_for_agent("AGENT-REG")
    await tool("echo warmup")

    # Ensure Config is initialized and task_type default dir points to tmp_path
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")

    class _DummyTaskType:
        def get_default_working_dir(self) -> Path:
            return tmp_path

    monkeypatch.setattr(
        ConfigSingleton.config, "task_type", _DummyTaskType(), raising=True
    )

    import useagent.tools.bash as bash_file

    await bash_file._restart_bash_session_using_config_directory()

    result = await bash_tool("pwd")
    assert isinstance(result, CLIResult)
    assert result.output.strip() == str(tmp_path)


@pytest.mark.skip
@pytest.mark.asyncio
@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.time_sensitive
async def test_python_here_doc_should_execute_without_timeout(
    tmp_path: Path, monkeypatch
):
    # TODO: This does timeout, but should not, I am not sure why. This needs to be revisited.
    init_bash_tool(str(tmp_path))
    tool = make_bash_tool_for_agent("AGENT-REG")

    cmd = r"""
/usr/bin/env python3 - <<'PY'
import importlib.metadata as m, json
pkgs = ["pytest","click","httpx","httpcore","openai","uvicorn","attrs","aiohttp","python-dotenv","coverage","jinja2","werkzeug","flit_core","tox","mypy","ruff","pre_commit"]
out={}
for p in pkgs:
  try:
    out[p]=m.version(p)
  except Exception:
    out[p]=None
print(json.dumps(out))
PY
""".strip()

    result = await tool(cmd)
    assert isinstance(result, CLIResult)

    parsed: dict[str, str | None] = json.loads(result.output.strip().splitlines()[-1])
    assert "pytest" in parsed


@pytest.mark.asyncio
@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.slow
async def test_stderr_flood_should_not_deadlock(tmp_path: Path):
    init_bash_tool(str(tmp_path))
    tool = make_bash_tool_for_agent("AGENT-REG")

    cmd = (
        'python3 -c "import sys; '
        "[sys.stderr.write('x'*1024) for _ in range(20000)]\""
    )
    result = await tool(cmd)
    assert isinstance(result, CLIResult)
    assert result.error and isinstance(result.error, str)
