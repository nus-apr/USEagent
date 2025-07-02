from pathlib import Path
from string import Template

from pydantic_ai import Agent, RunContext
from pydantic_ai.tools import Tool
from pydantic_ai.providers.openai import OpenAIProvider

from useagent.config import ConfigSingleton, AppConfig
from useagent.state.git_repo import GitRepository
from useagent.state.state import Location, TaskState
from useagent.tools.bash import bash_tool
from useagent.microagents.decorators import alias_for_microagents

from typing import Final
AGENT_ID: Final[str] = "SEARCH"
SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()

@alias_for_microagents(AGENT_ID)
def init_agent(config:AppConfig = ConfigSingleton.config) -> Agent:
    search_code_agent =  Agent(
        config.model,
        instructions=SYSTEM_PROMPT,
        deps_type=TaskState,
        output_type=list[Location],
        tools=[Tool(bash_tool)]
    )

    @search_code_agent.instructions
    def add_task_description(ctx: RunContext[TaskState]) -> str:
        """Add a task description to the TaskState.

        Args:
            ctx (RunContext[TaskState]): The context containing the task state.

        Returns:
            str: The issue statement of the task.
        """
        return ctx.deps.task.get_issue_statement()
    
    return search_code_agent
