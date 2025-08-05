from pathlib import Path

from loguru import logger
from pydantic_ai import Agent, RunContext
from pydantic_ai.tools import Tool

from useagent.config import AppConfig, ConfigSingleton
from useagent.microagents.decorators import (
    alias_for_microagents,
    conditional_microagents_triggers,
)
from useagent.microagents.management import load_microagents_from_project_dir
from useagent.pydantic_models.artifacts.test_result import TestResult
from useagent.pydantic_models.task_state import TaskState
from useagent.tools.bash import make_bash_tool_for_agent

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()


@conditional_microagents_triggers(load_microagents_from_project_dir())
@alias_for_microagents("TESTEXEC")
def init_agent(
    config: AppConfig | None = None,
) -> Agent[TaskState, TestResult]:

    if config is None:
        config = ConfigSingleton.config
    assert config is not None

    test_execution_agent = Agent(
        config.model,
        instructions=SYSTEM_PROMPT,
        retries=2,
        output_retries=3,
        deps_type=TaskState,
        output_type=TestResult,
        tools=[Tool(make_bash_tool_for_agent("TESTEXEC"), max_retries=7)],
    )

    @test_execution_agent.instructions
    def add_environment_command_information(ctx: RunContext[TaskState]) -> str:
        """Add a Info on the commands, if the TaskState contains an active Environment with them.

        Args:
            ctx (RunContext[TaskState]): The context containing the task state.

        Returns:
            str: Additional Information derived from `ActiveEnvironment` if possible.
        """
        if ctx.deps.active_environment and ctx.deps.active_environment.commands:
            cmds = ctx.deps.active_environment.commands
            return (
                "Here are some previously identified commands relevant for you and this project:"
                + f"\t {cmds.test_command} to run (general) project tests (you might want to narrow it down if possible)"
                if cmds.test_command
                else (
                    "\tTest Command: Unknown. You must derive it yourself."
                    + f"\t {cmds.run_command} to run the project and e.g. its build."
                    if cmds.run_command
                    else (
                        "\t Run Command: Unkown. You must derive it yourself, but it might not be important for testing."
                        + f"\t {cmds.linting_command} to run the projects linting"
                        if cmds.linting_command
                        else (
                            ""
                            + f"\t And example reduction of test scope was achievable with commands like this: {cmds.example_reduced_test_command}"
                            if cmds.reducable_test_scope
                            and cmds.example_reduced_test_command
                            else ""
                        )
                    )
                )
            )
        else:
            logger.warning(
                "[Agent] Tester Agent was called without an ActiveEnvironment that contains commands"
            )
            return "There is currently no information on the projects test- or build-commands. You will have to derive them yourself. Pay special attention to files like the README.md, .tomls, and other documentation files in the project root."

    @test_execution_agent.instructions
    def add_output_description(self) -> str:
        return (
            """
        ---------------------------
        Output:
        You should produce a `TestResult` summarizing all relevant tests.

        """
            + TestResult.get_output_instructions()
        )

    return test_execution_agent
