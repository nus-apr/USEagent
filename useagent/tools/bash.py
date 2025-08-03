"""
Bash tool.
"""

import asyncio
import os
from collections import deque
from collections.abc import Callable

from loguru import logger

from useagent.pydantic_models.common.constrained_types import NonEmptyStr
from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo


# TODO: Add a Tool for the MetaAgent to see the Bash History
class _BashSession:
    """A session of a bash shell."""

    _started: bool
    _process: asyncio.subprocess.Process

    command: str = "/bin/bash"
    _output_delay: float = 0.2  # seconds
    _timeout: float = 120.0  # seconds
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
                supplied_arguments={"command": command},
            )
        if self._process.returncode is not None:
            return CLIResult(
                system="tool must be restarted",
                error=f"bash has exited with returncode {self._process.returncode}",
            )
        if self._timed_out:
            return ToolErrorInfo(
                message=f"timed out: bash has not returned in {self._timeout} seconds and must be restarted",
                supplied_arguments={"command": command},
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
                supplied_arguments={"command": command},
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

    """Running Agent keeps track of the agent for history reasons."""
    _running_agent: NonEmptyStr = "UNK"

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
        # TODO: Introduce a global flag alongside 'use-empirical-otpimizations' etc. for these kind of patches based on errors to optimize.
        if command.startswith("grep -r ") and len(command.split()) < 4:
            return ToolErrorInfo(
                message="The supplied command is a grep -r, but did not specify enough other arguments. Please reconsider your strategy how to supply a string to your grep - or use a different command and approach.",
                supplied_arguments={"command": str(command), "restart": str(restart)},
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


def set_current_running_agent(agent: NonEmptyStr) -> None:
    """
    Sets the current running agents for history purposes.
    After this is set, all entries will get this agent as their corresponding author.
    Stays until either called again, or the BashTool gets reset.
    """
    if _bash_tool_instance:
        _bash_tool_instance._running_agent = agent


def __reset_bash_tool():
    """
    This method is only used for tests and testing purposes.
    Otherwise, with our `init_edit_tools` we introduce some side-effects that make tests a bit flaky.
    """
    global _bash_tool_instance
    _bash_tool_instance = None


async def bash_tool(command: NonEmptyStr) -> CLIResult | ToolErrorInfo:
    """Execute a bash command in the bash shell.

    Args:
        command (str): The command to execute.

    Returns:
        CLIResult: The result of the command execution.
    """
    logger.info(f"[Tool] Invoked bash_tool with command: {command}")
    assert _bash_tool_instance is not None, (
        "bash_tool_instance is not initialized. "
        "Call init_bash_tool() before using the bash tool."
    )
    try:
        result = await _bash_tool(command)
        _bash_tool_instance._bash_history.append(
            (command, _bash_tool_instance._running_agent, result)
        )
        return result
    except Exception as exc:
        # Just store the exception, but then throw it further
        # e.g. if its a ValueError this is an important part of the workflow
        _bash_tool_instance._bash_history.append(
            (command, _bash_tool_instance._running_agent, exc)
        )
        raise exc


async def _bash_tool(command: NonEmptyStr) -> CLIResult | ToolErrorInfo:
    assert _bash_tool_instance, "Bash Tool Instance was not set!"
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
