from pathlib import Path
from string import Template

from pydantic_ai import Agent, RunContext
from pydantic_ai.tools import Tool

from app.config import ConfigSingleton, AppConfig
from app.state.state import Location, TaskState, DiffEntry
from app.tools.edit import view, create, str_replace, insert, extract_diff


SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()

def init_agent(config:AppConfig = ConfigSingleton.config) -> Agent:
    # For locally hosted URLs
    provider_kwargs = (
        {"provider": OpenAIProvider(base_url=config.provider_url, api_key="ollama-dummy")}
        if config.provider_url
        else {}
    )
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
        ],
        **provider_kwargs
    )
