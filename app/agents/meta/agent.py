## NOTE: implment MeteAgent with agent delegation

from string import Template
from pydantic_ai import Agent, RunContext
from pydantic_ai.usage import UsageLimits
from pathlib import Path

from app import config

from app.state.state import TaskState, Location

from app.agents.search_code.agent import search_code_agent


SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()
# TODO: define the output type
meta_agent = Agent(config.model, instructions=SYSTEM_PROMPT, deps_type=TaskState, output_type=str)


## This adds the task description to instructions (SYSTEM prompt).
@meta_agent.instructions
def add_task_description(ctx: RunContext[TaskState]) -> str:
    """Add a task description to the TaskState.

    Args:
        task_description (str): The description of the task to be added.
    """
    return ctx.deps.task.get_issue_statement()


### Define actions as tools to meta_agent. Each action interfaces to another agent in Pydantic AI.


@meta_agent.tool
async def search_code(ctx: RunContext[TaskState], instruction: str) -> list[Location]:
    """Search for relevant locations in the codebase. Only search in source code files, not test files.

    Args:
        instruction (str): Instruction on what to search for in the codebase.

    Returns:
        list[Location]: List of locations in the codebase that match the search criteria.
    """
    r = await search_code_agent.run(instruction, deps=ctx.deps)
    return r.output


@meta_agent.tool
async def view_task_state(ctx: RunContext[TaskState]) -> str:
    """View the current task state.
    Use this tool to retrieve the up-to-date task state, including code locations, test locations, the diff store, and additional knowledge.

    Returns:
        str: The string representation of the current task state.
    """
    return ctx.deps.to_model_repr()


def agent_loop(task_state: TaskState):
    """
    Main agent loop.
    """
    result = meta_agent.run_sync("Invoke tools to complete the task", deps=task_state)

    return result.output