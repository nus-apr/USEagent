## NOTE: implment MetaAgent with agent delegation

from pathlib import Path
from string import Template

from loguru import logger
from pydantic_ai import Agent, RunContext
from pydantic_ai.usage import UsageLimits
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.tools import Tool

from useagent import config
from useagent.config import ConfigSingleton, AppConfig
from useagent.agents.edit_code.agent import init_agent as init_edit_code_agent
from useagent.agents.search_code.agent import init_agent as init_search_code_agent
from useagent.models.code import Location
from useagent.models.git import DiffEntry
from useagent.models.task_state import TaskState
from useagent.tools.bash import init_bash_tool
from useagent.tools.edit import init_edit_tools
from useagent.tools.base import ToolError
from useagent.tools.meta import select_diff_from_diff_store, view_task_state
from useagent.microagents.decorators import alias_for_microagents,conditional_microagents_triggers
from useagent.microagents.management import load_microagents_from_project_dir

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()
# TODO: define the output type

@conditional_microagents_triggers(load_microagents_from_project_dir())
@alias_for_microagents("META")
def init_agent(config:AppConfig = ConfigSingleton.config) -> Agent:
    meta_agent = Agent(
        config.model, 
        instructions=SYSTEM_PROMPT, 
        deps_type=TaskState,
        tools=[
            Tool(select_diff_from_diff_store,takes_ctx=True, max_retries=3),
            Tool(view_task_state,takes_ctx=True,max_retries=0)
        ],
        output_type=str
    )

    ## This adds the task description to instructions (SYSTEM prompt).
    @meta_agent.instructions
    def add_task_description(ctx: RunContext[TaskState]) -> str:
        """Add a task description to the TaskState.

        Args:
            task_description (str): The description of the task to be added.
        """
        return ctx.deps._task.get_issue_statement()

    ### Define actions as tools to meta_agent. Each action interfaces to another agent in Pydantic AI.
    @meta_agent.tool(retries=4)
    async def search_code(ctx: RunContext[TaskState], instruction: str) -> list[Location]:
        """Search for relevant locations in the codebase. Only search in source code files, not test files.

        Args:
            instruction (str): Comprehensive instruction for the search, including keywords, file types, and other criteria. Give as many details as possible to improve the search results.

        Returns:
            list[Location]: List of locations in the codebase that match the search criteria.
        """
        logger.info(f"[MetaAgent] Invoked search_code with instruction: {instruction}")
        search_code_agent = init_search_code_agent()
        r = await search_code_agent.run(instruction, deps=ctx.deps)
        res = r.output
        logger.info(f"[MetaAgent] search_code result: {res}")

        # update task state with the found code locations
        ctx.deps.code_locations.extend(res)

        return res


    @meta_agent.tool(retries=4)
    async def edit_code(ctx: RunContext[TaskState], instruction: str) -> DiffEntry:
        """Edit the codebase based on the provided instruction.

        Args:
            instruction (str): Instruction for the code edit. The instrution should be very specific, typically should include where in the codebase to edit (files, lines, etc.), what to change, and how to change it.

        Returns:
            str: A unified diff of the changes that can be applied to the codebase.
        """
        logger.info(f"[MetaAgent] Invoked edit_code with instruction: {instruction}")
        edit_code_agent = init_edit_code_agent()
        r = await edit_code_agent.run(instruction, deps=ctx.deps)
        res = r.output
        logger.info(f"[MetaAgent] edit_code result: {res}")

        # update task state with the diff
        diff_id = ctx.deps.diff_store.add_entry(res)
        logger.info(f"[MetaAgent] Added diff entry with ID: {diff_id}")

        return res
    ### Action definitions END


    return meta_agent


def agent_loop(task_state: TaskState):
    """
    Main agent loop.
    """
    # first initialize some of the tools based on the task.
    init_bash_tool(
        task_state._task.get_working_directory(),
        command_transformer=task_state._task.command_transformer,
    )
    init_edit_tools(task_state._task.get_working_directory())
    meta_agent = init_agent()
    # actually running the agent

    #TODO: This is for the meta-agent, but it would make sense that every agent gets a configurable amount of retries. 
    # At the moment, an inside-edit-code-agent will also restart at the meta-agent level.
    # I tried to wrap it in a function, but there are two issues: 
    #    1) The other agents are async, so the function must be Async too
    #    2) The types must match for pydantic to work flawlessly, so a retry that returns ANY does not work, and there are no good Functional-Generics in Python.
    maximum_allowed_tool_errors : int = 25
    tool_errors: int = 0
    while tool_errors < maximum_allowed_tool_errors:
        try:
            result = meta_agent.run_sync("Invoke tools to complete the task.", deps=task_state)
        except ToolError as e:
            logger.debug(f"[MetaAgent] Received a Tool Error {e.message}. Re-Prompting (error #{tool_errors} of {maximum_allowed_tool_errors})")
            prompt = f"Previous tool call was done poorly: {e.message}. Try again."
            tool_errors = tool_errors + 1

    return result.output
