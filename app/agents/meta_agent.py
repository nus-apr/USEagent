

## NOTE: implment MeteAgent with agent delegation

from pydantic_ai import Agent, RunContext
from pydantic_ai.usage import UsageLimits

from app import config

from app.state.state import TaskState, Location

SYSTEM_PROMPT = (

)

meta_agent = Agent(config.model, system_prompt=SYSTEM_PROMPT, deps_type=TaskState)



### Define actions as tools to meta_agent. Each action interfaces to another agent in Pydantic AI.

@meta_agent.tool
async def search_code(ctx: RunContext[TaskState], instruction: str) -> list[Location]:
    """Search for relevant locations in the codebase. Only search in source code files, not test files.

    Args:
        instruction (str): Instruction on what to search for in the codebase.

    Returns:
        list[Location]: List of locations in the codebase that match the search criteria.
    """
    pass