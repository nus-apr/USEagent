from pathlib import Path
from string import Template

from pydantic_ai import Agent, RunContext
from pydantic_ai.tools import Tool
from pydantic_ai.providers.openai import OpenAIProvider

from useagent.config import ConfigSingleton, AppConfig
from useagent.models.code import Location
from useagent.models.git import DiffEntry
from useagent.models.task_state import TaskState
from useagent.tools.edit import view, create, str_replace, insert, extract_diff
from useagent.microagents.decorators import alias_for_microagents,conditional_microagents_triggers
from useagent.microagents.management import load_microagents_from_project_dir

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()

@conditional_microagents_triggers(load_microagents_from_project_dir())
@alias_for_microagents("EDIT")
def init_agent(config:AppConfig = ConfigSingleton.config) -> Agent:
    agent = Agent(
        config.model,
        instructions=SYSTEM_PROMPT,
        deps_type=TaskState,
        output_type=DiffEntry,
        tools=[
            Tool(view),
            Tool(create),
            Tool(str_replace),
            Tool(insert),
            Tool(extract_diff),
        ]
    )
    return agent