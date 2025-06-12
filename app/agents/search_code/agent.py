from pathlib import Path
from string import Template

from pydantic_ai import Agent, RunContext
from pydantic_ai.tools import Tool

from app.config import ConfigSingleton
from app.state.git_repo import GitRepository
from app.state.state import Location, TaskState
from app.tools.bash import bash_tool

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()

search_code_agent = Agent(
        ConfigSingleton.config.model,
        instructions=SYSTEM_PROMPT,
        deps_type=TaskState,
        output_type=list[Location],
        tools=[Tool(bash_tool)],
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


# def init_agent(task_state: TaskState) -> Agent[GitRepository, list[Location]]:
#     sys_prompt = Template(SYSTEM_PROMPT).substitute(
#         task=task_state.task.get_issue_statement()
#     )
#     search_code_agent = Agent(
#         config.model,
#         instructions=sys_prompt,
#         deps_type=GitRepository,
#         output_type=list[Location],
#         tools=[Tool(bash_tool)],
#     )
#     return search_code_agent
