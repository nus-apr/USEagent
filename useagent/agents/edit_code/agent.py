from pathlib import Path
from string import Template

from pydantic_ai import Agent, RunContext
from pydantic_ai.tools import Tool
from pydantic_ai.providers.openai import OpenAIProvider

from useagent.config import ConfigSingleton, AppConfig
from useagent.state.state import Location, TaskState, DiffEntry
from useagent.tools.edit import view, create, str_replace, insert, extract_diff
from useagent.microagents.management import alias_for_microagents

from typing import Final
AGENT_ID: Final[str] = "EDIT"

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()

@alias_for_microagents(AGENT_ID)
def init_agent(config:AppConfig = ConfigSingleton.config) -> Agent:
    return Agent(
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