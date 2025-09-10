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

import useagent.common.constants as constants
from useagent.common.command_utility import has_heredoc, validate_heredoc
from useagent.common.context_window import fit_message_into_context_window
from useagent.common.guardrails import useagent_guard_rail
from useagent.config import ConfigSingleton
from useagent.pydantic_models.common.constrained_types import NonEmptyStr
from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ArgumentEntry, ToolErrorInfo


class _BashSession:
    """A session of a bash shell."""

    _started: bool
    _process: asyncio.subprocess.Process

    command: str = "/bin/bash"

    _timeout: float = constants.BASH_TOOL_DEFAULT_MAX_TIMEOUT
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

        # This was observed in tests - usually there should always be an existing directory coming from the Task Type. In tests this was not necessarily the case.
        if init_dir:
            init_dir_path = Path(init_dir)
            if not init_dir_path.exists() or not init_dir_path.is_dir():
                init_dir_path.mkdir(parents=True, exist_ok=True)

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
        # terminate only if still running
        if self._process.returncode is None:
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

            if (
                ConfigSingleton.is_initialized()
                and ConfigSingleton.config.optimization_toggles[
                    "block-long-multiline-commands"
                ]
            ):
                if (
                    command.count("\n")
                    > constants.BASH_TOOL_MAX_LINE_LENGTH_FOR_EOF_COMMANDS
                    or len(command.splitlines())
                    > constants.BASH_TOOL_MAX_LINE_LENGTH_FOR_EOF_COMMANDS
                ):
                    return ToolErrorInfo(
                        message="You provided a large multi-line command. Such commands are currently intentionally de-actived, please refer from using them and prefer a sequence of short, simple commands, or consider different tools to write file-content. The command was not executed.",
                        supplied_arguments=[ArgumentEntry("command", command)],
                    )

            if has_heredoc(command):
                if not validate_heredoc(command):
                    # DevNote: See Issue 29 and the related test-suite.
                    return ToolErrorInfo(
                        message="You tried to provide a command including a heredoc / EOF marker. Either due to your mistake, or a backend processing, the provided command does not result in a valid encoding and will not be executed. Consider if there are other strategies to achieve your goal (e.g. writing a file first with a different tool). If you need to perform the command you want to execute in exactly this matter, revisit its encoding with the background that it needs to be encoded to utf-8.",
                        supplied_arguments=[ArgumentEntry("command", command)],
                    )
                logger.debug(
                    "Received a command with an EOF marker - reducing timeout to only allow short commands"
                )
                self._timeout = constants.BASH_TOOL_REDUCED_TIMEOUT_FOR_EOF_COMMANDS

            # See Issue #40, Hotfix
            if command.startswith("rg") or " rg " in command:
                self._timeout = constants.BASH_TOOL_REDUCED_TIMEOUT_FOR_RG_COMMANDS

            # Build the command by encoding the intial command and add our 'finish' sentinel after.
            effective_command = (
                command.encode("UTF-8", "") + f"; echo '{self._sentinel}'\n".encode()
            )
            # DevNote: Below is where the actual command is passed in, this is our `run(effective_command)`
            self._process.stdin.write(effective_command)

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

                    if len(output) > constants.BASH_TOOL_OUTPUT_MAX_LENGTH:
                        # DevNote: See Issue #31, we move this from a ValueError to a ToolOutPutError
                        logger.warning(
                            f"[Tool] Bash Tool tried to execute a command with large output (Command was {command})"
                        )
                        return ToolErrorInfo(
                            message="command exceeded a healthy output window (10MB)",
                            supplied_arguments=[ArgumentEntry("command", command)],
                        )
            except TimeoutError:
                self._timed_out = True
                logger.warning(
                    f"[Tool] Bash timed out after {self._timeout} for command {command}"
                )
                return ToolErrorInfo(
                    message=f"timed out: bash has not returned in {self._timeout} seconds and must be restarted",
                    supplied_arguments=[ArgumentEntry("command", command)],
                )
            finally:
                self._timeout = (
                    constants.BASH_TOOL_DEFAULT_MAX_TIMEOUT
                )  # TimeOuts might have changed for EOF
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
            fit_message_into_context_window(
                output,
                safety_buffer=constants.BASH_TOOL_MESSAGE_RESPONSE_CONTEXT_LENGTH_BUFFER,
            )
            if isinstance(output, str)
            else output
        )
        error = (
            fit_message_into_context_window(
                error,
                safety_buffer=constants.BASH_TOOL_MESSAGE_RESPONSE_CONTEXT_LENGTH_BUFFER,
            )
            if isinstance(error, str)
            else error
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
                await _restart_bash_session_using_config_directory()

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
    _PRINT_MAX_LENGTH_IN_LINES: int = 50

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
        if len(output_by_lines) > constants.COMMAND_OUTPUT_MAX_PRINT_CUT_OFF:
            to_log = "\n".join(
                output_by_lines[: constants.COMMAND_OUTPUT_MAX_PRINT_CUT_OFF // 2]
                + [
                    "[[ shortened in log for readability, presented in full for agent ]]"
                ]
                + output_by_lines[-(constants.COMMAND_OUTPUT_MAX_PRINT_CUT_OFF // 2) :]
            )
        else:
            to_log = result.output
        logger.info(
            f"[Tool] bash_tool {'shortened' if len(output_by_lines) > constants.COMMAND_OUTPUT_MAX_PRINT_CUT_OFF else ''} result: output={to_log}, error={result.error}"
        )
    else:
        if result.error == "bash has exited with returncode 2":
            logger.warning(
                f"[Tool] the provided bash command {command} resulted in a bash-internal timeout (return code 2)"
            )
            await _restart_bash_session_using_config_directory()
            return ToolErrorInfo(
                message="Your command made the bash session timeout ('bash has exited with returncode 2'), no results could be retrieved and the bash has been restarted.",
                supplied_arguments=[ArgumentEntry("command", str(command))],
            )
        elif result.error == "bash has exited with returncode 127":
            # DevNote: Sometimes the BashTool can reach an un-restorable case after poor commands (merging total commands in stdin). This will be seen by this error code.
            # See Issue #36 on this. The source is currently unknown, but restarting the bash cannot harm on a normal unknown command.
            logger.warning(
                "[Tool] Bashtool has tried to execute an unkown command - restarting it to avoid getting stuck in unknown commands"
            )
            await _restart_bash_session_using_config_directory()
            return ToolErrorInfo(
                message="Your commands (possibly previous comands) lead to a faulty state in the bash tool. The BashTool has now been restarted. Please revisit your commands, and avoid commands with offset output.",
                supplied_arguments=[ArgumentEntry("command", command)],
            )
        else:
            logger.info(
                f"[Tool] bash_tool result: output={result.output}, error={result.error}"
            )

    return result


async def _restart_bash_session_using_config_directory():
    if not _bash_tool_instance or not _bash_tool_instance._session:
        logger.error("Tried to restart a bash session, but no bash was initialized.")
        raise RuntimeError(
            "Tried to restart a bash session, but no bash was initialized."
        )

    logger.debug("[Tool] Bash Session is being restarted")
    # discard old session entirely
    _bash_tool_instance._session.stop()
    _bash_tool_instance._session = _BashSession()
    bash_tool_init_dir: Path | None = (
        ConfigSingleton.config.task_type.get_default_working_dir()
        if ConfigSingleton.is_initialized()
        else None
    )
    await _bash_tool_instance._session.start(
        init_dir=str(bash_tool_init_dir) if bash_tool_init_dir else None
    )
    logger.debug(
        f"[Tool] Successfully restarted Bash Tool. New session starts in "
        f"{str(bash_tool_init_dir) if bash_tool_init_dir else '<<UNKNOWN>>'}"
    )


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
