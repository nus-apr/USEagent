import pytest

from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo
from useagent.tools.bash import _BashSession


@pytest.mark.time_sensitive
@pytest.mark.tool
@pytest.mark.regression
@pytest.mark.asyncio
async def test_bash_session_should_timeout_on_long_running_command(tmp_path):
    session = _BashSession()
    session._timeout = 1.0  # force timeout at 1s
    await session.start(str(tmp_path))

    result = await session.run("sleep 2")

    assert isinstance(result, ToolErrorInfo)
    assert "timed out" in result.message


@pytest.mark.time_sensitive
@pytest.mark.tool
@pytest.mark.regression
@pytest.mark.asyncio
async def test_bash_session_should_timeout_and_set_a_timeout_flag(tmp_path):
    session = _BashSession()
    session._timeout = 1.0  # force timeout at 1s
    await session.start(str(tmp_path))

    result = await session.run("sleep 2")
    assert result
    assert session._timed_out


@pytest.mark.time_sensitive
@pytest.mark.tool
@pytest.mark.regression
@pytest.mark.asyncio
async def test_bash_session_should_remain_timed_out_after_initial_timeout(tmp_path):
    session = _BashSession()
    session._timeout = 1.0
    await session.start(str(tmp_path))

    result1 = await session.run("sleep 2")
    assert isinstance(result1, ToolErrorInfo)
    assert "timed out" in result1.message

    # DevNote: This is a benign command, that should never fail, but if the shell already timed out it will fail unless restarted.
    result2 = await session.run("echo hello world")
    assert isinstance(result2, ToolErrorInfo)
    assert "timed out" in result2.message


@pytest.mark.time_sensitive
@pytest.mark.tool
@pytest.mark.regression
@pytest.mark.asyncio
async def test_bash_session_should_not_time_out_after_restart(tmp_path):
    session = _BashSession()
    session._timeout = 2.0
    await session.start(str(tmp_path))

    result1 = await session.run("sleep 3")
    assert isinstance(result1, ToolErrorInfo)
    assert "timed out" in result1.message

    session.stop()
    await session.start(str(tmp_path))
    assert session._started

    # DevNote: This is a benign command, that should never fail, but if the shell already timed out it will fail unless restarted.
    result2 = await session.run("echo hello")
    assert not isinstance(result2, ToolErrorInfo)


@pytest.mark.time_sensitive
@pytest.mark.tool
@pytest.mark.regression
@pytest.mark.asyncio
async def test_bash_session_should_complete_command_within_timeout(tmp_path):
    session = _BashSession()
    session._timeout = 3.0  # set generous timeout
    await session.start(str(tmp_path))

    result = await session.run("sleep 1")

    assert isinstance(result, CLIResult)
    assert not isinstance(result, ToolErrorInfo)
    assert result.output is not None
    assert not session._timed_out


@pytest.mark.time_sensitive
@pytest.mark.tool
@pytest.mark.asyncio
async def test_bash_session_should_run_multiple_commands_when_not_timed_out(tmp_path):
    session = _BashSession()
    session._timeout = 3.0
    await session.start(str(tmp_path))

    result1 = await session.run("sleep 1")
    assert isinstance(result1, CLIResult)

    result2 = await session.run("echo hello world")
    assert isinstance(result2, CLIResult)
    assert "hello world" in result2.output


@pytest.mark.time_sensitive
@pytest.mark.tool
@pytest.mark.asyncio
async def test_bash_session_should_run_multiple_commands_with_restart_in_between(
    tmp_path,
):
    session = _BashSession()
    session._timeout = 3.0
    await session.start(str(tmp_path))

    result1 = await session.run("sleep 1")
    assert isinstance(result1, CLIResult)

    session.stop()
    await session.start(str(tmp_path))

    result2 = await session.run("echo hello world")
    assert isinstance(result2, CLIResult)
    assert "hello world" in result2.output


@pytest.mark.tool
@pytest.mark.asyncio
async def test_bash_session_should_fail_when_not_started(tmp_path):
    session = _BashSession()
    result = await session.run("echo should fail")

    assert isinstance(result, ToolErrorInfo)
    assert "Session has not started" in result.message


@pytest.mark.tool
@pytest.mark.asyncio
async def test_bash_session_can_be_stopped(tmp_path):
    session = _BashSession()
    assert not session._started
    await session.start(str(tmp_path))
    assert session._started
    session.stop()
    assert not session._started


@pytest.mark.tool
@pytest.mark.asyncio
async def test_bash_session_check_timeout_after_stop(tmp_path):
    session = _BashSession()
    session._timeout = 3.0

    await session.start(str(tmp_path))
    session.stop()

    assert session._timeout == 3.0


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_bash_session_should_fail_after_stop_not_due_to_timeout(tmp_path):
    session = _BashSession()
    session._timeout = 1.0

    await session.start(str(tmp_path))
    session.stop()

    result = await session.run("echo test")
    assert isinstance(result, ToolErrorInfo)
    assert "time" not in result.message


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_bash_session_should_fail_due_to_session_not_started(tmp_path):
    session = _BashSession()
    session._timeout = 1.0

    await session.start(str(tmp_path))
    session.stop()

    result = await session.run("echo test")
    assert isinstance(result, ToolErrorInfo)
    assert "Session has not started" in result.message


@pytest.mark.time_sensitive
@pytest.mark.tool
@pytest.mark.regression
@pytest.mark.asyncio
async def test_bash_session_timeout_sets_new_folder(tmp_path):
    session = _BashSession()
    session._timeout = 1.0
    await session.start(str(tmp_path))

    result1 = await session.run("sleep 2")
    assert isinstance(result1, ToolErrorInfo)
    assert "timed out" in result1.message

    # DevNote: This is a benign command, that should never fail, but if the shell already timed out it will fail unless restarted.
    result2 = await session.run("pwd")
    assert isinstance(result2, ToolErrorInfo)
    assert "timed out" in result2.message
