"""
Bash tool.
"""

import asyncio
import os
import time
from collections import deque
from collections.abc import Awaitable, Callable
from pathlib import Path

from loguru import logger

from useagent.common.context_window import fit_message_into_context_window
from useagent.config import ConfigSingleton
from useagent.pydantic_models.common.constrained_types import NonEmptyStr
from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ArgumentEntry, ToolErrorInfo
from useagent.tools.common import useagent_guard_rail


class _BashSession:
    """A session of a bash shell."""

    _started: bool
    _process: asyncio.subprocess.Process

    command: str = "/bin/bash"
    _output_delay: float = 0.1  # seconds
    # DevNote: The timeout is quite large, but we have seen commands that need so long
    # An example is `apt-get install openjdk-jdk-8` or similar large packages.
    _timeout: float = 2400.0  # seconds
    _sentinel: str = "<<exit>>"

    def __init__(self):
        self._started = False
        self._timed_out = False
        self._lock = asyncio.Lock()

    async def start(self, init_dir: str | None = None):
        if self._started:
            return

        if (
            init_dir
            and (guard_rail_tool_error := useagent_guard_rail(init_dir)) is not None
        ):
            return guard_rail_tool_error

        self._process: asyncio.subprocess.Process = (
            await asyncio.create_subprocess_shell(
                self.command,
                preexec_fn=os.setsid,
                shell=True,
                bufsize=0,
                cwd=init_dir,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        )

        self._started = True

    def stop(self):
        """Terminate the bash shell."""
        if not self._started:
            return ToolErrorInfo(message="Session has not started.")
        if self._process.returncode is not None:
            return
        self._process.terminate()
        self._started = False
        if self._timed_out:
            self._timed_out = False

    async def run(self, command: str):
        """Execute a command in the bash shell."""

        async def read_stream(stream, buf, sentinel=None):
            while True:
                data = await stream.read(4096)
                if not data:
                    break
                buf.extend(data)
                if sentinel and sentinel in buf:
                    return True
            return False

        async with self._lock:
            if not self._started:
                return ToolErrorInfo(
                    message="Session has not started.",
                    supplied_arguments=[ArgumentEntry("command", command)],
                )
            if self._process.returncode is not None:
                return CLIResult(
                    system="tool must be restarted",
                    error=f"bash has exited with returncode {self._process.returncode}",
                )
            if self._timed_out:
                return ToolErrorInfo(
                    message=f"timed out: bash has not returned in {self._timeout} seconds and must be restarted",
                    supplied_arguments=[ArgumentEntry("command", command)],
                )

            if (
                guard_rail_tool_error := useagent_guard_rail(
                    command, supplied_arguments=[ArgumentEntry("command", command)]
                )
            ) is not None:
                return guard_rail_tool_error

            # we know these are not None because we created the process with PIPEs
            assert self._process.stdin
            assert self._process.stdout
            assert self._process.stderr

            # send command to the process
            self._process.stdin.write(
                command.encode() + f"; echo '{self._sentinel}'\n".encode()
            )
            await self._process.stdin.drain()
            stdout_buf, stderr_buf = bytearray(), bytearray()
            sentinel_bytes = self._sentinel.encode()

            # read output from the process, until the sentinel is found
            try:
                async with asyncio.timeout(self._timeout):
                    # # read stdout & stderr concurrently
                    tasks = [
                        asyncio.create_task(
                            read_stream(
                                self._process.stdout, stdout_buf, sentinel_bytes
                            )
                        ),
                        asyncio.create_task(
                            read_stream(self._process.stderr, stderr_buf)
                        ),
                    ]
                    done, pending = await asyncio.wait(
                        tasks, return_when=asyncio.FIRST_COMPLETED
                    )
                    # if sentinel found, cancel others
                    for task in done:
                        if task.result() is True:
                            for t in pending:
                                t.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    output = stdout_buf.decode(errors="replace").replace(
                        self._sentinel, ""
                    )
                    stderr_content = stderr_buf.decode(errors="replace")

                    if len(output) > 10000000:  # e.g., 10MB limit
                        raise ValueError("Output exceeds limit; command aborted")
                    # if we read directly from stdout/stderr, it will wait forever for
                    # EOF. use the StreamReader buffer directly instead.
                    # output = (
                    #    self._process.stdout._buffer.decode()  # pyright: ignore[reportAttributeAccessIssue]
                    # )  # pyright: ignore[reportAttributeAccessIssue]
                    # if self._sentinel in output:
                    #    # strip the sentinel and break
                    #    output = output[: output.index(self._sentinel)]
                    #    break
            except TimeoutError:
                self._timed_out = True
                logger.warning(
                    f"[Tool] Bash timed out after {self._timeout} for command {command}"
                )
                return ToolErrorInfo(
                    message=f"timed out: bash has not returned in {self._timeout} seconds and must be restarted",
                    supplied_arguments=[ArgumentEntry("command", command)],
                )
            if output.endswith("\n"):
                output = output[:-1]
            error = stderr_content
            if error.endswith("\n"):
                error = error[:-1]

            # clear the buffers so that the next output can be read correctly
            output = (
                output if output else None
            )  # Make empty output properly None for Type Checking
            if not error and not output:
                output = f"(Command {command} finished silently)"

        error = (
            error if error else None
        )  # Make empty output properly None for Type Checking
        output = (
            output if output else None
        )  # Make empty output properly None for Type Checking
        if not error and not output:
            output = f"(Command {command} finished silently)"

        # Possibly: Command outputs can be large / noisy, and exceed the context window.
        # We account for them by optionally shortening them, if configured (See Issue #30)
        output = (
            fit_message_into_context_window(output)
            if isinstance(output, str)
            else output
        )
        error = (
            fit_message_into_context_window(error) if isinstance(error, str) else error
        )

        return CLIResult(output=output, error=error)


class BashTool:
    """
    A tool that allows the agent to run bash commands.
    """

    _session: _BashSession | None

    """ 
    Bash History gets recorded and consists of:
        - the command
        - the agent that called it (if visible / possible)
        - the result, or error it created 
    """
    _bash_history: deque[
        tuple[NonEmptyStr, NonEmptyStr, CLIResult | ToolErrorInfo | Exception]
    ]

    """Default working directory for the bash session."""
    default_working_dir: str

    """A function that transforms the command before it is executed."""
    command_transformer: Callable[[str], str]

    def __init__(
        self,
        default_working_dir: str,
        command_transformer: Callable[[str], str] = lambda x: x,
    ):
        self._session = None
        self.default_working_dir = default_working_dir
        self.command_transformer = command_transformer
        self._bash_history = deque(maxlen=250)

    async def __call__(
        self, command: str | None = None, restart: bool = False, **kwargs
    ) -> CLIResult | ToolErrorInfo:
        if restart:
            if self._session:
                self._session.stop()
            self._session = _BashSession()
            await self._session.start(self.default_working_dir)

            return CLIResult(system="tool has been restarted.")

        if self._session is None:
            self._session = _BashSession()
            await self._session.start(self.default_working_dir)

        if not command:
            return ToolErrorInfo(message="No Command Supplied")
        # DevNote: This is a common issue witnessed, it tries to call `grep -r 'some_pattern'` which is invalid.
        # The resulting grep-error-message seems unsufficient for the model to be unerstandable.
        if (
            ConfigSingleton.is_initialized()
            and ConfigSingleton.config.optimization_toggles[
                "check-grep-command-arguments"
            ]
            and command.startswith("grep -r ")
            and len(command.split()) < 4
        ):
            return ToolErrorInfo(
                message="The supplied command is a grep -r, but did not specify enough other arguments. Please reconsider your strategy how to supply a string to your grep - or use a different command and approach.",
                supplied_arguments=[
                    ArgumentEntry("command", command),
                    ArgumentEntry("restart", str(restart)),
                ],
            )

        # It can run into greps that take ages because it checks all files in hidden repositories.
        # A good example is `grep -r 'test' .` that will also look into all files of .venv and .git
        if (
            ConfigSingleton.is_initialized()
            and ConfigSingleton.config.optimization_toggles[
                "hide-hidden-folders-from-greps"
            ]
            and command.startswith("grep")
        ):
            logger.debug(
                "[Tool] Bash Tool added exceptions for hidden folders and files to a grep command."
            )
            command = 'grep --exclude-dir=".*" --exclude=".*" ' + command[4:]
        if (
            ConfigSingleton.is_initialized()
            and ConfigSingleton.config.optimization_toggles[
                "hide-hidden-folders-from-finds"
            ]
            and command.startswith("find .")
        ):
            logger.debug(
                "[Tool] Bash Tool added exceptions for hidden folders and files to a find command."
            )
            command = 'find . -type d -name ".*" -prune -o ' + command[6:]

        transformed_command = self.command_transformer(command)
        return await self._session.run(transformed_command)


_bash_tool_instance: BashTool | None = None


def init_bash_tool(
    default_working_dir: str, command_transformer: Callable[[str], str] = lambda x: x
) -> None:
    """Initialize a bash tool instance. Must be called before registering any bash tool to any agent."""
    global _bash_tool_instance
    _bash_tool_instance = BashTool(default_working_dir, command_transformer)


def __reset_bash_tool():
    """
    This method is only used for tests and testing purposes.
    Otherwise, with our `init_edit_tools` we introduce some side-effects that make tests a bit flaky.
    """
    global _bash_tool_instance
    _bash_tool_instance = None


def make_bash_tool_for_agent(
    agent_name: str = "UNK", bash_call_delay_in_seconds: float = 0.0
) -> Callable[[NonEmptyStr], Awaitable[CLIResult | ToolErrorInfo]]:
    # DevNote:
    # This wrapper allows us to give each Agent its own, labelled (but identical) Bash Tool for logging & recording reasons.
    # If we just say `bash_tool(command,agent)` then the Agents would call it and use different variables.
    # If we set it with a _set_running_agent(agent) then only the last agent would be recalled.
    # I also looked into using the stack trace, but the tools are only in the pydantic ai framework, and do not call e.g. search_code_agent.py:xx
    #
    # So this is a bit complex, but it preserves all attributes that we want.
    # In general, we can pass more `closures` into the bash tool this way, while keeping the same interface towards the agent.
    async def bash_tool(command: NonEmptyStr) -> CLIResult | ToolErrorInfo:
        """Execute a bash command in the bash shell.

        Args:
            command (str): The command to execute.

        Returns:
            CLIResult: The result of the command execution.
        """
        logger.info(f"[{agent_name} - Tool] Invoked bash_tool with command: {command}")
        assert _bash_tool_instance is not None, "bash_tool_instance is not initialized."
        try:
            # DevNote:
            # It might be possible to have a `restart bash tool`, but to be honest why would you ever not want to restart it?
            # Automatically restart the tool if it had timed out before calling again.
            if _bash_tool_instance._session and _bash_tool_instance._session._timed_out:
                logger.warning(
                    "Current Bash Tool was in a timed-out state - restarting it"
                )
                _bash_tool_instance._session.stop()
                bash_tool_init_dir: Path | None = (
                    ConfigSingleton.config.task_type.get_default_working_dir()
                    if ConfigSingleton.is_initialized()
                    else None
                )
                await _bash_tool_instance._session.start(
                    init_dir=str(bash_tool_init_dir)
                )
                logger.debug(
                    f"Successfully restarted Bash Tool. New session starts in {str(bash_tool_init_dir) if bash_tool_init_dir else '<<UNKNOWN>>'}"
                )

            result = await _bash_tool(command, bash_call_delay_in_seconds)
            _bash_tool_instance._bash_history.append((command, agent_name, result))
            return result
        except Exception as exc:
            _bash_tool_instance._bash_history.append((command, agent_name, exc))
            raise exc

    bash_tool.__name__ = "bash_tool"
    bash_tool.__doc__ = make_bash_tool_for_agent.__annotations__.get(
        "__doc__", bash_tool.__doc__
    )
    return bash_tool


# Simple instance to keep backward compatability. Sets the agent to `UNK` but all other functionality is identical.
bash_tool: Callable[[NonEmptyStr], Awaitable[CLIResult | ToolErrorInfo]] = (
    make_bash_tool_for_agent()
)


async def _bash_tool(
    command: NonEmptyStr, delay_in_seconds: float = 0.0
) -> CLIResult | ToolErrorInfo:
    assert _bash_tool_instance, "Bash Tool Instance was not set!"

    # DevNote:
    # Depending on your Provider and Account, there might be a limit on how many requests you can send to the model per second / minute.
    # For most calls, this is not a big issue, because the calls will take a while etc.
    # But for some of our agents and tools, it can rapid-fire simple commands (like looking for dependencies, echoing things, etc.)
    # And we'll hit this limit. So, for some agents (Probing Agent, VCS Agent) we add a speed bumper. Also: See Issue #16
    if (
        ConfigSingleton.is_initialized()
        and ConfigSingleton.config.optimization_toggles["bash-tool-speed-bumper"]
        and delay_in_seconds > 0
    ):
        if delay_in_seconds > 2.0:
            logger.warning(
                f"[Tool] Received a high {delay_in_seconds}s timeout between bash calls."
            )
        time.sleep(delay_in_seconds)

    result = await _bash_tool_instance(command)
    if result and isinstance(result, ToolErrorInfo):
        return result

    if (
        result
        and result.output
        and ConfigSingleton.is_initialized()
        and ConfigSingleton.config.optimization_toggles["shorten-log-output"]
    ):
        output_by_lines = result.output.splitlines()
        if len(output_by_lines) > 80:
            to_log = "\n".join(
                output_by_lines[:40]
                + [
                    "[[ shortened in log for readability, presented in full for agent ]]"
                ]
                + output_by_lines[-40:]
            )
        else:
            to_log = result.output
        logger.info(
            f"[Tool] bash_tool shortened result: output={to_log}, error={result.error}"
        )
    else:
        logger.info(
            f"[Tool] bash_tool result: output={result.output}, error={result.error}"
        )

    return result


def get_bash_history() -> (
    list[tuple[NonEmptyStr, NonEmptyStr, CLIResult | ToolErrorInfo | Exception]]
):
    """
    Retrieve information of the BashTool, gathered accross agents.

    Returns:
        List[Tuple[str,str,CLIResult | ToolErrorInfo | Exception]]: The last 50 recorded commands, the agent that executed it and their results, errors or exceptions.

    """
    if _bash_tool_instance is None:
        return []
    return list(_bash_tool_instance._bash_history)


async def test_lsR_slow_behavior():
    """Test function to reproduce the long runtime with ls -R in _BashSession."""
    # Create a temporary directory with some nested structure
    temp_dir = "../playground"
    try:
        base = Path(temp_dir)
        # Initialize Bash session
        session = _BashSession()
        await session.start(init_dir=str(base))

        # Run ls -R

        result = await session.run(
            "mvn dependency:get  -DgroupId=com.google.guava  -DartifactId=guava  -Dversion=32.1.2-jre  -U --no-transfer-progress "
        )
        print(result)

        session.stop()

    finally:
        pass


async def test_python_code_exec():
    cmd = """ 
/usr/bin/python - <<'PY'
import importlib.metadata as m, json
pkgs = ["pytest","click","httpx","httpcore","openai","uvicorn","attrs","aiohttp","python-dotenv","coverage","jinja2","werkzeug","flit_core","tox","mypy","ruff","pre_commit"]
out={}
for p in pkgs:
  try:
    out[p]=m.version(p)
  except Exception as e:
    out[p]=None
print(json.dumps(out))
"""

    temp_dir = "../playground"
    base = Path(temp_dir)
    session = _BashSession()
    await session.start(init_dir=str(base))

    # Run ls -R

    result = await session.run(cmd)
    print(result)

    session.stop()


async def test_deadlock():
    sess = _BashSession()
    await sess.start()
    # This writes a lot to stderr, enough to fill the pipe buffer.
    cmd = (
        "python3 -c \"import sys; [sys.stderr.write('x'*1024) for _ in range(100000)]\""
    )
    result = await sess.run(cmd)
    print("Result:", result)


# Run the test
# if __name__ == "__main__":
#     asyncio.run(test_deadlock())
