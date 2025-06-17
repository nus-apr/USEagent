from pathlib import Path
from string import Template

from pydantic_ai import Agent, RunContext
from pydantic_ai.tools import Tool

from app.config import ConfigSingleton, AppConfig
from app.state.git_repo import GitRepository
from app.state.state import Location, TaskState
from app.tools.bash import bash_tool

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()

def init_agent(config:AppConfig = ConfigSingleton.config) -> Agent:
    # For locally hosted URLs
    provider_kwargs = (
        {"provider": OpenAIProvider(base_url=config.provider_url, api_key="ollama-dummy")}
        if config.provider_url
        else {}
    )
    search_code_agent =  Agent(
        config.model,
        instructions=SYSTEM_PROMPT,
        deps_type=TaskState,
        output_type=list[Location],
        tools=[Tool(bash_tool)],
        **provider_kwargs
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
