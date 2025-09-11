import asyncio
import json
import shlex
import subprocess
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


@pytest.mark.slow
@pytest.mark.time_sensitive
@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_issue_29_bash_tool_command_with_eof_sign_should_not_timeout_example_other_command_with_apt_packages(
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


@pytest.mark.asyncio
@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.time_sensitive
async def test_issue_29_python_here_doc_with_a_raw_string_markershould_execute_with_timeout(
    tmp_path: Path, monkeypatch
):
    # See Issue 29, the raw string r'\n' becomes '\\n' after encoding, which then fails the EOF marker.
    # THis one is extra strange, the .strip() makes it timeout ...
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
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(tool(cmd), timeout=5)


@pytest.mark.asyncio
@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.time_sensitive
async def test_issue_29_python_here_doc_with_a_raw_string_markershould_execute_and_give_a_CLIResult(
    tmp_path: Path, monkeypatch
):
    # See Issue 29, the raw string r'\n' becomes '\\n' after encoding, which then fails the EOF marker.
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
"""
    result = await asyncio.wait_for(tool(cmd), timeout=5)
    assert result and isinstance(result, CLIResult)


@pytest.mark.asyncio
@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.time_sensitive
async def test_issue_29_python_here_doc_with_manual_specified_linebreak_should_execute_without_timeout(
    tmp_path: Path, monkeypatch
):
    #  Issue 29
    init_bash_tool(str(tmp_path))
    tool = make_bash_tool_for_agent("AGENT-REG")

    cmd = """
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
PY\n
"""
    result = await asyncio.wait_for(tool(cmd), timeout=15)
    assert isinstance(result, CLIResult)

    parsed: dict[str, str | None] = json.loads(result.output.strip().splitlines()[-1])
    assert "pytest" in parsed


@pytest.mark.asyncio
@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.time_sensitive
async def test_issue_29_python_here_doc_with_manual_specified_linebreak_with_raw_string_should_give_tool_error_due_to_encoding(
    tmp_path: Path, monkeypatch
):
    #  Issue 29, the raw string r'PY\n' turns through decode into 'PY\\n' breaking the EOF marker and logic.
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
PY\n
"""
    result = await asyncio.wait_for(tool(cmd), timeout=5)

    assert isinstance(result, ToolErrorInfo)
    assert "heredoc" in result.message.lower()


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


@pytest.mark.asyncio
@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.slow
async def test_output_flood_should_abort_quickly_on_large_stdout(tmp_path: Path):
    init_bash_tool(str(tmp_path))
    tool = make_bash_tool_for_agent("AGENT-OVERFLOW-PORTABLE")

    # Warmup to ensure session is up
    await tool("echo warmup")

    # Produce ~32 MiB quickly on macOS; BSD head supports -c
    # This is large enough to trip typical caps but still quick.
    cmd = r"head -c 33554432 /dev/zero | tr '\0' x"

    result = await tool(cmd)

    assert isinstance(result, ToolErrorInfo)


@pytest.mark.asyncio
@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.time_sensitive
async def test_issue_29_python_here_doc_with_long_command_and_give_a_CLIResult(
    tmp_path: Path, monkeypatch
):
    # See Issue 29, the raw string r'\n' becomes '\\n' after encoding, which then fails the EOF marker.
    # Seen on 02.09.
    init_bash_tool(str(tmp_path))
    tool = make_bash_tool_for_agent("AGENT-REG")

    init_bash_tool(str(tmp_path))
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["block-long-multiline-commands"] = False

    cmd: str = """
cat > run_test.sh <<'SCRIPT'
#!/usr/bin/env bash
set -vxE

# Non-interactive
export DEBIAN_FRONTEND=noninteractive

# Update and install common build/test dependencies
apt-get update -y
apt-get install -y --no-install-recommends \
  build-essential git curl wget ca-certificates \
  python3 python3-venv python3-pip \
  nodejs npm \
  default-jdk maven gradle \
  golang-go cmake cargo pkg-config libssl-dev || true

# Ensure pip tools
python3 -m pip install --upgrade pip setuptools wheel pytest tox || true

ROOT_DIR="$(pwd)"
echo "Project root: ${ROOT_DIR}"

# Track overall status
STATUS=0

# Python: look for indicators and run tests
if [ -f "requirements.txt" ] || [ -f "pyproject.toml" ] || ls *.py >/dev/null 2>&1; then
  echo "Detected potential Python project"
  python3 -m venv .venv || true
  . .venv/bin/activate || true
  if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt || STATUS=1
  fi
  # install test tools if pytest present
  pip install pytest || true
  # Run pytest if tests directory or files exist
  if [ -d "tests" ] || ls test_*.py >/dev/null 2>&1 || ls *_test.py >/dev/null 2>&1; then
    pytest -q || STATUS=1
  else
    echo "No pytest tests detected"
  fi
  deactivate || true
fi

# Node.js: package.json -> npm test
if [ -f "package.json" ]; then
  echo "Detected Node.js project"
  npm ci --no-audit --no-fund || STATUS=1
  if npm test --silent; then
    echo "npm tests completed"
  else
    echo "npm tests failed or not defined"
    STATUS=1
  fi
fi

# Maven: pom.xml
if [ -f "pom.xml" ]; then
  echo "Detected Maven project"
  mvn -B test || STATUS=1
fi

# Gradle: build.gradle or settings.gradle
if ls build.gradle* settings.gradle* >/dev/null 2>&1; then
  echo "Detected Gradle project"
  # Use Gradle wrapper if present
  if [ -x ./gradlew ]; then
    ./gradlew test || STATUS=1
  else
    gradle test || STATUS=1
  fi
fi

# Go
if [ -f "go.mod" ] || ls *.go >/dev/null 2>&1; then
  echo "Detected Go project"
  go test ./... || STATUS=1
fi

# Rust
if [ -f "Cargo.toml" ]; then
  echo "Detected Rust project"
  cargo test || STATUS=1
fi

# C/C++ CMake
if [ -f "CMakeLists.txt" ]; then
  echo "Detected CMake project"
  mkdir -p build && cd build
  cmake .. || STATUS=1
  make -j"$(nproc)" || STATUS=1
  if command -v ctest >/dev/null 2>&1; then
    ctest --output-on-failure || STATUS=1
  fi
  cd "${ROOT_DIR}"
fi

# If no known project files found, print helpful info
if ! ( [ -f "requirements.txt" ] || [ -f "pyproject.toml" ] || [ -f "package.json" ] || [ -f "pom.xml" ] || ls build.gradle* settings.gradle* >/dev/null 2>&1 || [ -f "go.mod" ] || [ -f "Cargo.toml" ] || [ -f "CMakeLists.txt" ] ); then
  echo "No recognized project type files found. Listing top-level files:"
  ls -la
fi

exit ${STATUS}
SCRIPT
"""
    result = await asyncio.wait_for(tool(cmd), timeout=15)
    assert result and isinstance(result, CLIResult)


@pytest.mark.asyncio
@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.time_sensitive
async def test_block_long_commands_for_the_eof_files(tmp_path: Path, monkeypatch):
    # Variation: We introduced a flag to filter any long command, this one should be cought by it.
    init_bash_tool(str(tmp_path))
    tool = make_bash_tool_for_agent("AGENT-REG")

    init_bash_tool(str(tmp_path))
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["block-long-multiline-commands"] = True

    cmd: str = """
cat > run_test.sh <<'SCRIPT'
#!/usr/bin/env bash
set -vxE

# Non-interactive
export DEBIAN_FRONTEND=noninteractive

# Update and install common build/test dependencies
apt-get update -y
apt-get install -y --no-install-recommends \
  build-essential git curl wget ca-certificates \
  python3 python3-venv python3-pip \
  nodejs npm \
  default-jdk maven gradle \
  golang-go cmake cargo pkg-config libssl-dev || true

# Ensure pip tools
python3 -m pip install --upgrade pip setuptools wheel pytest tox || true

ROOT_DIR="$(pwd)"
echo "Project root: ${ROOT_DIR}"

# Track overall status
STATUS=0

# Python: look for indicators and run tests
if [ -f "requirements.txt" ] || [ -f "pyproject.toml" ] || ls *.py >/dev/null 2>&1; then
  echo "Detected potential Python project"
  python3 -m venv .venv || true
  . .venv/bin/activate || true
  if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt || STATUS=1
  fi
  # install test tools if pytest present
  pip install pytest || true
  # Run pytest if tests directory or files exist
  if [ -d "tests" ] || ls test_*.py >/dev/null 2>&1 || ls *_test.py >/dev/null 2>&1; then
    pytest -q || STATUS=1
  else
    echo "No pytest tests detected"
  fi
  deactivate || true
fi

# Node.js: package.json -> npm test
if [ -f "package.json" ]; then
  echo "Detected Node.js project"
  npm ci --no-audit --no-fund || STATUS=1
  if npm test --silent; then
    echo "npm tests completed"
  else
    echo "npm tests failed or not defined"
    STATUS=1
  fi
fi

# Maven: pom.xml
if [ -f "pom.xml" ]; then
  echo "Detected Maven project"
  mvn -B test || STATUS=1
fi

# Gradle: build.gradle or settings.gradle
if ls build.gradle* settings.gradle* >/dev/null 2>&1; then
  echo "Detected Gradle project"
  # Use Gradle wrapper if present
  if [ -x ./gradlew ]; then
    ./gradlew test || STATUS=1
  else
    gradle test || STATUS=1
  fi
fi

# Go
if [ -f "go.mod" ] || ls *.go >/dev/null 2>&1; then
  echo "Detected Go project"
  go test ./... || STATUS=1
fi

# Rust
if [ -f "Cargo.toml" ]; then
  echo "Detected Rust project"
  cargo test || STATUS=1
fi

# C/C++ CMake
if [ -f "CMakeLists.txt" ]; then
  echo "Detected CMake project"
  mkdir -p build && cd build
  cmake .. || STATUS=1
  make -j"$(nproc)" || STATUS=1
  if command -v ctest >/dev/null 2>&1; then
    ctest --output-on-failure || STATUS=1
  fi
  cd "${ROOT_DIR}"
fi

# If no known project files found, print helpful info
if ! ( [ -f "requirements.txt" ] || [ -f "pyproject.toml" ] || [ -f "package.json" ] || [ -f "pom.xml" ] || ls build.gradle* settings.gradle* >/dev/null 2>&1 || [ -f "go.mod" ] || [ -f "Cargo.toml" ] || [ -f "CMakeLists.txt" ] ); then
  echo "No recognized project type files found. Listing top-level files:"
  ls -la
fi

exit ${STATUS}
SCRIPT
"""
    result = await asyncio.wait_for(tool(cmd), timeout=15)
    assert result and isinstance(result, ToolErrorInfo)


@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.time_sensitive
async def test_eof_sleep_command_should_timeout(tmp_path: Path):
    init_bash_tool(str(tmp_path))
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["bash-tool-speed-bumper"] = True

    tool = make_bash_tool_for_agent(bash_call_delay_in_seconds=0.1)
    await tool("echo warmup")

    import useagent.tools.bash as bash_file

    _bash_tool_instance = bash_file._bash_tool_instance
    assert _bash_tool_instance

    _bash_tool_instance._session._timeout = 2  # shorter than the sleep below

    cmd = """
/bin/bash - <<'SH'
set -e
sleep 10
echo done
SH
"""
    result = await tool(cmd)

    assert isinstance(result, ToolErrorInfo)
    assert "time" in result.message.lower()
    assert _bash_tool_instance._session._timed_out


@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.time_sensitive
async def test_eof_sleep_timeout_should_recover_and_reset_session(tmp_path: Path):
    init_bash_tool(str(tmp_path))
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["bash-tool-speed-bumper"] = True

    tool = make_bash_tool_for_agent(bash_call_delay_in_seconds=0.1)
    await tool("echo warmup")

    import useagent.tools.bash as bash_file

    _bash_tool_instance = bash_file._bash_tool_instance
    assert _bash_tool_instance

    # force short timeout to trigger
    _bash_tool_instance._session._timeout = 2
    cmd = """
/bin/bash - <<'SH'
set -e
sleep 10
echo done
SH
"""
    result = await tool(cmd)
    assert isinstance(result, ToolErrorInfo)
    assert _bash_tool_instance._session._timed_out

    # now run a simple hello command, expecting recovery
    result2 = await tool("echo hello")
    assert isinstance(result2, CLIResult)
    assert "hello" in result2.output

    # after restart, timeout should be reset to a sane default (e.g. >100s)
    assert _bash_tool_instance._session._timeout > 100
    assert not _bash_tool_instance._session._timed_out


@pytest.mark.asyncio
@pytest.mark.tool
@pytest.mark.regression
async def test_meson_command_should_fail_with_exit_127_without_timeout(tmp_path: Path):
    # See Issue 36 - BashTool can bring itself in a continious 127 state
    # But this seems to be related to async behaviour, as below test shows.

    host_check = subprocess.run(
        ["bash", "-lc", "meson --version"],
        capture_output=True,
        text=True,
    )
    if host_check.returncode == 0:
        pytest.skip("meson is available on the host; skipping test")

    init_bash_tool(str(tmp_path))
    tool = make_bash_tool_for_agent("AGENT-MESON")

    result = await tool("meson --version")
    result = await tool("meson --version")
    assert isinstance(result, CLIResult)
    assert not result.output or result.output.strip() == ""
    assert isinstance(result.error, str) and "command not found" in result.error

    import useagent.tools.bash as bash_file

    _bash_tool_instance = bash_file._bash_tool_instance
    assert _bash_tool_instance
    assert not _bash_tool_instance._session._timed_out


@pytest.mark.asyncio
@pytest.mark.tool
@pytest.mark.regression
async def test_meson_command_should_error_command_not_found_without_timeout(
    tmp_path: Path,
):
    # See Issue 36 - BashTool can bring itself in a continious 127 state
    import shutil
    import subprocess

    if (
        shutil.which("meson")
        or subprocess.run(
            ["bash", "-lc", "command -v meson >/dev/null 2>&1"]
        ).returncode
        == 0
    ):
        pytest.skip("meson is available on the host; skipping")

    init_bash_tool(str(tmp_path))
    tool = make_bash_tool_for_agent("AGENT-MESON")

    result = await tool("meson --version")
    assert isinstance(result, CLIResult)
    assert (result.output is None) or (result.output.strip() == "")
    assert isinstance(result.error, str) and "command not found" in result.error

    import useagent.tools.bash as bash_file

    assert bash_file._bash_tool_instance
    assert not bash_file._bash_tool_instance._session._timed_out


@pytest.mark.asyncio
@pytest.mark.tool
@pytest.mark.regression
async def test_meson_command_suppressed_stderr_should_finish_silently(tmp_path: Path):
    # See Issue 36 - BashTool can bring itself in a continious 127 state
    import shutil
    import subprocess

    if (
        shutil.which("meson")
        or subprocess.run(
            ["bash", "-lc", "command -v meson >/dev/null 2>&1"]
        ).returncode
        == 0
    ):
        pytest.skip("meson is available on the host; skipping")

    init_bash_tool(str(tmp_path))
    tool = make_bash_tool_for_agent("AGENT-MESON")

    result = await tool("meson --version 2>/dev/null")
    assert isinstance(result, CLIResult)
    assert result.error is None
    assert isinstance(result.output, str) and "finished silently" in result.output


@pytest.mark.asyncio
@pytest.mark.tool
@pytest.mark.regression
async def test_exit_127_should_restart_into_config_dir(tmp_path: Path, monkeypatch):
    init_bash_tool(str(tmp_path))

    # Ensure Config is initialized so restart uses task_type.get_default_working_dir()
    from useagent.config import ConfigSingleton

    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")

    class _DummyTaskType:
        def get_default_working_dir(self) -> Path:
            return tmp_path

    monkeypatch.setattr(
        ConfigSingleton.config, "task_type", _DummyTaskType(), raising=True
    )

    tool = make_bash_tool_for_agent("AGENT-EXIT127")

    warmup = await tool("echo warmup")
    assert isinstance(warmup, CLIResult)

    # Kill the shell with 127
    _ = await tool("exit 127")

    # First call after exit: wrapper surfaces returncode 127 and restarts
    first_after = await tool("pwd")
    assert isinstance(first_after, ToolErrorInfo)

    # Second call: should succeed in restarted session, in tmp_path, and we get CLIResults.
    second_after = await tool("pwd")
    assert isinstance(second_after, CLIResult)
    assert second_after.error is None
    assert second_after.output.strip() == str(tmp_path)

    import useagent.tools.bash as bash_file

    _bash_tool_instance = bash_file._bash_tool_instance
    assert _bash_tool_instance
    assert not _bash_tool_instance._session._timed_out


@pytest.mark.asyncio
@pytest.mark.tool
async def test_stop_marks_session_stopped_even_if_proc_already_exited(tmp_path: Path):
    init_bash_tool(str(tmp_path))
    tool = make_bash_tool_for_agent("AGENT-STOP")
    await tool("exit 0")
    import useagent.tools.bash as bash_file

    sess = bash_file._bash_tool_instance._session
    assert sess and sess._process.returncode is not None
    sess.stop()
    assert sess._started is False


@pytest.mark.asyncio
@pytest.mark.tool
async def test_restart_helper_recreates_session_process(tmp_path: Path):
    init_bash_tool(str(tmp_path))
    tool = make_bash_tool_for_agent("AGENT-RESTART")
    await tool("echo warmup")
    import useagent.tools.bash as bash_file

    s = bash_file._bash_tool_instance._session
    pid_before = s._process.pid
    await bash_file._restart_bash_session_using_config_directory()
    pid_after = bash_file._bash_tool_instance._session._process.pid
    assert pid_before != pid_after


@pytest.mark.time_sensitive
@pytest.mark.regression
@pytest.mark.asyncio
@pytest.mark.tool
@pytest.mark.timeout(20)  # in s
async def test_issue_40_observed_timeouting_rg_command(tmp_path: Path):
    init_bash_tool(str(tmp_path))
    tool = make_bash_tool_for_agent("AGENT-RESTART")
    result = await tool(
        """rg "pytest|tox|nox|ansible-test|setup" -n --hidden --glob '!venv' || true"""
    )

    assert result


@pytest.mark.time_sensitive
@pytest.mark.regression
@pytest.mark.asyncio
@pytest.mark.tool
@pytest.mark.timeout(20)  # in s
async def test_issue_40_observed_timeouting_rg_command_variant_2(tmp_path: Path):
    # Exact 2nd example we observed in logs
    init_bash_tool(str(tmp_path))
    tool = make_bash_tool_for_agent("AGENT-RESTART")
    result = await tool(
        """rg "pytest|unittest|tox|pdm run|uv run --group test|pytest" -n --hidden --glob '!venv' || true"""
    )

    assert result


@pytest.mark.time_sensitive
@pytest.mark.regression
@pytest.mark.asyncio
@pytest.mark.tool
@pytest.mark.timeout(20)  # in s
async def test_issue_40_observed_timeouting_rg_command_without_hidden(
    tmp_path: Path,
):
    init_bash_tool(str(tmp_path))
    tool = make_bash_tool_for_agent("AGENT-RESTART")
    result = await tool(
        """rg "pytest|tox|nox|ansible-test|setup" -n --glob '!venv' || true"""
    )

    assert result


@pytest.mark.time_sensitive
@pytest.mark.regression
@pytest.mark.asyncio
@pytest.mark.tool
@pytest.mark.timeout(20)  # in s
async def test_issue_40_rg_with_scope_should_finish_fast(tmp_path: Path) -> None:
    init_bash_tool(str(tmp_path))
    tool = make_bash_tool_for_agent("AGENT-RESTART")
    cmd = "rg \"pytest|tox|nox|ansible-test|setup\" -n --glob '!venv' . || true"
    r = await tool(cmd)
    assert isinstance(r, CLIResult)


@pytest.mark.time_sensitive
@pytest.mark.regression
@pytest.mark.asyncio
@pytest.mark.tool
@pytest.mark.timeout(20)  # in s
async def test_issue_40_rg_with_cd_and_scoped_should_finish_fast(
    tmp_path: Path,
) -> None:
    init_bash_tool(str(tmp_path))
    tool = make_bash_tool_for_agent("AGENT-RESTART")
    cmd = (
        f"cd {shlex.quote(str(tmp_path))} && "
        "env -u RIPGREP_CONFIG_PATH rg --no-config "
        "\"pytest|tox|nox|ansible-test|setup\" -n --glob '!venv' . || true"
    )
    r = await tool(cmd)
    assert isinstance(r, CLIResult)


@pytest.mark.asyncio
@pytest.mark.tool
@pytest.mark.parametrize("code", [0, 1, 100, 127, 110, 141])
async def test_issue_42_nonzero_exit_should_surface_then_recover(
    tmp_path: Path, code: int
):
    init_bash_tool(str(tmp_path))
    tool = make_bash_tool_for_agent("AGENT-EXITCODES")

    # Call 1: Kill the Shell - It will finish successfully and give us a result about finishing silently
    res1 = await tool(f"exit {code}")
    print(res1)
    assert isinstance(res1, CLIResult)

    # Call 2: Will see the stopped shell, print error and restart
    res2 = await tool("echo hello")
    assert isinstance(res2, ToolErrorInfo)

    # Call 3: Shell was restarted after Call 2, and is back up and normal again.
    res3 = await tool("echo hello")
    assert isinstance(res3, CLIResult)
    assert "hello" in res3.output


@pytest.mark.asyncio
@pytest.mark.tool
@pytest.mark.parametrize("code", [0, 1, 100, 127, 110, 141])
async def test_issue_42_nonzero_exit_wrapped_in_bash_should_surface_then_recover(
    tmp_path: Path, code: int
):
    init_bash_tool(str(tmp_path))
    tool = make_bash_tool_for_agent("AGENT-EXITCODES")

    res1 = await tool(f"bash -c 'exit {code}'")
    print(res1)
    assert isinstance(res1, CLIResult)

    # DevNote: When wrapped in bash, only the sub-sub-process is killed, not our bash.
    # So we get immediate results, and no need to restart anything.
    res2 = await tool("echo hello")
    assert isinstance(res2, CLIResult)
