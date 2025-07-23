from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.tools import Tool

from useagent.config import AppConfig, ConfigSingleton
from useagent.microagents.decorators import (
    alias_for_microagents,
    conditional_microagents_triggers,
)
from useagent.microagents.management import load_microagents_from_project_dir
from useagent.pydantic_models.info.environment import Environment
from useagent.pydantic_models.task_state import TaskState
from useagent.tools.bash import bash_tool

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()


@conditional_microagents_triggers(load_microagents_from_project_dir())
@alias_for_microagents("PROBE")
def init_agent(
    config: AppConfig | None = None,
) -> Agent[TaskState, Environment]:

    if config is None:
        config = ConfigSingleton.config
    assert config is not None

    environment_probing_agent = Agent(
        config.model,
        instructions=SYSTEM_PROMPT,
        deps_type=TaskState,
        output_type=Environment,
        tools=[Tool(bash_tool)],
    )

    return environment_probing_agent
