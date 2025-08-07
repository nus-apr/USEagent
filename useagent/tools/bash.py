"""
Bash tool.
"""

import asyncio
import os
import time
from collections import deque
from collections.abc import Awaitable, Callable

from loguru import logger

from useagent.config import ConfigSingleton
from useagent.pydantic_models.common.constrained_types import NonEmptyStr
from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ArgumentEntry, ToolErrorInfo


class _BashSession:
    """A session of a bash shell."""

    _started: bool
    _process: asyncio.subprocess.Process

    command: str = "/bin/bash"
    _output_delay: float = 0.2  # seconds
    _timeout: float = 1200.0  # seconds
    _sentinel: str = "<<exit>>"

    def __init__(self):
        self._started = False
        self._timed_out = False

    async def start(self, init_dir: str | None = None):
        if self._started:
            return

        self._process = await asyncio.create_subprocess_shell(
            self.command,
            preexec_fn=os.setsid,
            shell=True,
            bufsize=0,
            cwd=init_dir,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        self._started = True

    def stop(self):
        """Terminate the bash shell."""
        if not self._started:
            return ToolErrorInfo(message="Session has not started.")
        if self._process.returncode is not None:
            return
        self._process.terminate()

    async def run(self, command: str):
        """Execute a command in the bash shell."""
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

        # we know these are not None because we created the process with PIPEs
        assert self._process.stdin
        assert self._process.stdout
        assert self._process.stderr

        # send command to the process
        self._process.stdin.write(
            command.encode() + f"; echo '{self._sentinel}'\n".encode()
        )
        await self._process.stdin.drain()

        # read output from the process, until the sentinel is found
        try:
            async with asyncio.timeout(self._timeout):
                while True:
                    await asyncio.sleep(self._output_delay)
                    # if we read directly from stdout/stderr, it will wait forever for
                    # EOF. use the StreamReader buffer directly instead.
                    output = (
                        self._process.stdout._buffer.decode()  # pyright: ignore[reportAttributeAccessIssue]
                    )  # pyright: ignore[reportAttributeAccessIssue]
                    if self._sentinel in output:
                        # strip the sentinel and break
                        output = output[: output.index(self._sentinel)]
                        break
        except TimeoutError:
            self._timed_out = True
            return ToolErrorInfo(
                message=f"timed out: bash has not returned in {self._timeout} seconds and must be restarted",
                supplied_arguments=[ArgumentEntry("command", command)],
            )

        if output.endswith("\n"):
            output = output[:-1]

        error = (
            self._process.stderr._buffer.decode()  # pyright: ignore[reportAttributeAccessIssue]
        )  # pyright: ignore[reportAttributeAccessIssue]
        if error.endswith("\n"):
            error = error[:-1]

        # clear the buffers so that the next output can be read correctly
        self._process.stdout._buffer.clear()  # pyright: ignore[reportAttributeAccessIssue]
        self._process.stderr._buffer.clear()  # pyright: ignore[reportAttributeAccessIssue]

        error = (
            error if error else None
        )  # Make empty output properly None for Type Checking
        output = (
            output if output else None
        )  # Make empty output properly None for Type Checking
        if not error and not output:
            output = f"(Command {command} finished silently)"

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
        self._bash_history = deque(maxlen=50)

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
