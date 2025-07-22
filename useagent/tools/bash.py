"""
Bash tool.
"""

import asyncio
import os
from collections.abc import Callable

from loguru import logger

from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo


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
            return ToolErrorInfo(
                tool="Run",
                message="Session has not started.",
                supplied_arguments={k: str(v) for k, v in locals().items()},
            )
        if self._process.returncode is not None:
            return
        self._process.terminate()

    async def run(self, command: str):
        """Execute a command in the bash shell."""
        if not self._started:
            return ToolErrorInfo(
                tool="Run",
                message="Session has not started.",
                supplied_arguments={k: str(v) for k, v in locals().items()},
            )
        if self._process.returncode is not None:
            return CLIResult(
                system="tool must be restarted",
                error=f"bash has exited with returncode {self._process.returncode}",
            )
        if self._timed_out:
            return ToolErrorInfo(
                tool="Run",
                message=f"timed out: bash has not returned in {self._timeout} seconds and must be restarted",
                supplied_arguments={k: str(v) for k, v in locals().items()},
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
                tool="Run",
                message=f"timed out: bash has not returned in {self._timeout} seconds and must be restarted",
                supplied_arguments={k: str(v) for k, v in locals().items()},
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

        return CLIResult(output=output, error=error)


class BashTool:
    """
    A tool that allows the agent to run bash commands.
    """

    _session: _BashSession | None

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

        if command is not None:
            transformed_command = self.command_transformer(command)
            return await self._session.run(transformed_command)

        return ToolErrorInfo(
            tool="__Call__",
            message="No Command Supplied",
            supplied_arguments={k: str(v) for k, v in locals().items()},
        )


_bash_tool_instance: BashTool | None = None


def init_bash_tool(
    default_working_dir: str, command_transformer: Callable[[str], str] = lambda x: x
) -> None:
    """Initialize a bash tool instance. Must be called before registering any bash tool to any agent."""
    global _bash_tool_instance
    _bash_tool_instance = BashTool(default_working_dir, command_transformer)


async def bash_tool(command: str) -> CLIResult | ToolErrorInfo:
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

    result = await _bash_tool_instance(command)
    if isinstance(result, ToolErrorInfo):
        return result

    logger.info(
        f"[Tool] bash_tool result: output={result.output}, error={result.error}"
    )

    return result
