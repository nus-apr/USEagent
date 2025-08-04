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
from useagent.pydantic_models.info.partial_environment import PartialEnvironment
from useagent.tools.bash import bash_tool
from useagent.tools.probing import check_environment, report_environment

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()


@conditional_microagents_triggers(load_microagents_from_project_dir())
@alias_for_microagents("PROBE")
def init_agent(
    config: AppConfig | None = None,
) -> Agent[PartialEnvironment, Environment]:

    if config is None:
        config = ConfigSingleton.config
    assert config is not None

    # DevNote:
    # Initially, the probing agent was just meant to return a `Environment` using Bash,
    # but that is too difficult for the agent without doing it `step by step`.
    # To support this incremental building, we introduced a PartialEnvironment that is stored in the deps.
    # It can be checked and transformed with a little tool.
    # Just using the Environment for incremental building, because that requires a mutable element,
    # Which might lead to consistency issues (i.e. at the moment a environment is a clear tuple that is collected together at one point of time.)

    environment_probing_agent = Agent(
        config.model,
        instructions=SYSTEM_PROMPT,
        deps_type=PartialEnvironment,
        output_type=Environment,
        tools=[
            Tool(bash_tool, max_retries=5),
            Tool(report_environment, takes_ctx=True, max_retries=2),
            Tool(check_environment, takes_ctx=True, max_retries=1),
        ],
    )

    return environment_probing_agent
