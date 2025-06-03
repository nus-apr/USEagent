from pydantic_ai import Agent, RunContext
from pydantic_ai.tools import Tool
from app import config
from app.state.git_repo import GitRepository
from app.tools.bash import bash_tool

SYSTEM_PROMPT = ()

search_code_agent = Agent(
    config.model,
    system_prompt=SYSTEM_PROMPT,
    deps_type=GitRepository,
    tools=[Tool(bash_tool)],
)
