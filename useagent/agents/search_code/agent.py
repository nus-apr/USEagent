from pathlib import Path

from pydantic_ai import Agent, RunContext
from pydantic_ai.tools import Tool

import useagent.common.constants as constants
from useagent.common.context_window import fit_messages_into_context_window
from useagent.config import AppConfig, ConfigSingleton
from useagent.microagents.decorators import (
    alias_for_microagents,
    conditional_microagents_triggers,
)
from useagent.microagents.management import load_microagents_from_project_dir
from useagent.pydantic_models.artifacts.code import Location
from useagent.pydantic_models.task_state import TaskState
from useagent.tools.bash import make_bash_tool_for_agent

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()


@conditional_microagents_triggers(load_microagents_from_project_dir())
@alias_for_microagents("SEARCH")
def init_agent(
    config: AppConfig | None = None,
) -> Agent[TaskState, list[Location]]:

    if config is None:
        config = ConfigSingleton.config
    assert config is not None

    search_code_agent = Agent(
        config.model,
        instructions=SYSTEM_PROMPT,
        deps_type=TaskState,
        output_type=list[Location],
        tools=[
            Tool(
                make_bash_tool_for_agent(
                    "SEARCH",
                    bash_call_delay_in_seconds=constants.VCS_AGENT_BASH_TOOL_DELAY,
                ),
                max_retries=4,
            )
        ],
        history_processors=[fit_messages_into_context_window],
    )

    @search_code_agent.instructions
    def add_task_description(ctx: RunContext[TaskState]) -> str:
        """Add a task description to the TaskState.

        Args:
            ctx (RunContext[TaskState]): The context containing the task state.

        Returns:
            str: The issue statement of the task.
        """
        return ctx.deps._task.get_issue_statement()

    @search_code_agent.instructions
    def add_output_description(self) -> str:
        return (
            """
        ---------------------------
        Output:
        You should give a list of Location as the relevant locations.

        """
            + Location.get_output_instructions()
        )

    return search_code_agent
