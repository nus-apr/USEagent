from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.tools import Tool

import useagent.common.constants as constants
from useagent.config import AppConfig, ConfigSingleton
from useagent.microagents.decorators import (
    alias_for_microagents,
    conditional_microagents_triggers,
)
from useagent.microagents.management import load_microagents_from_project_dir
from useagent.pydantic_models.artifacts.git.diff import DiffEntry
from useagent.pydantic_models.task_state import TaskState
from useagent.tools.edit import (
    create,
    insert,
    read_file_as_diff,
    replace_file,
    str_replace,
    view,
)
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
        retries=constants.EDIT_CODE_AGENT_RETRIES,
        output_retries=constants.EDIT_CODE_AGENT_OUTPUT_RETRIES,
        tools=[
            Tool(view),
            Tool(create),
            Tool(str_replace),
            Tool(insert),
            Tool(extract_diff, takes_ctx=True),
            Tool(read_file_as_diff, takes_ctx=True),
            Tool(replace_file),
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
