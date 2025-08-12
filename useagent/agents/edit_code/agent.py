from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.tools import Tool

from useagent.config import AppConfig, ConfigSingleton
from useagent.microagents.decorators import (
    alias_for_microagents,
    conditional_microagents_triggers,
)
from useagent.microagents.management import load_microagents_from_project_dir
from useagent.pydantic_models.artifacts.git import DiffEntry
from useagent.pydantic_models.task_state import TaskState
from useagent.tools.edit import create, insert, str_replace, view
from useagent.tools.git import extract_diff

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()


@conditional_microagents_triggers(load_microagents_from_project_dir())
@alias_for_microagents("EDIT")
def init_agent(
    config: AppConfig | None = None,
) -> Agent[TaskState, DiffEntry]:
    if config is None:
        config = ConfigSingleton.config
    assert config is not None

    agent = Agent(
        config.model,
        instructions=SYSTEM_PROMPT,
        deps_type=TaskState,
        output_type=DiffEntry,
        retries=3,
        output_retries=12,  # DevNote: The diff-entries are hard to get right for the model. But they must fit their schema to make any sense.
        tools=[
            Tool(view),
            Tool(create),
            Tool(str_replace),
            Tool(insert),
            Tool(extract_diff),
        ],
    )

    @agent.instructions
    def add_output_instructions(self) -> str:
        return (
            """
        ------------------------------------------------
        Output:
        Your expected output is a `DiffEntry`. 
        """
            + DiffEntry.get_output_instructions()
        )

    return agent
