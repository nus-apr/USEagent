## NOTE: implment MetaAgent with agent delegation

from pathlib import Path
from string import Template

from loguru import logger
from pydantic_ai import Agent, RunContext
from pydantic_ai.usage import UsageLimits
from pydantic_ai.providers.openai import OpenAIProvider

from useagent import config
from useagent.config import ConfigSingleton, AppConfig
from useagent.agents.edit_code.agent import init_agent as init_edit_code_agent
from useagent.agents.search_code.agent import init_agent as init_search_code_agent
from useagent.state.state import DiffEntry, Location, TaskState
from useagent.tools.bash import init_bash_tool
from useagent.tools.edit import init_edit_tools
from useagent.tools.base import ToolError
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
        output_type=str
    )

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


    @meta_agent.tool
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

    @meta_agent.tool
    async def view_task_state(ctx: RunContext[TaskState]) -> str:
        """View the current task state.
        Use this tool to retrieve the up-to-date task state, including code locations, test locations, the diff store, and additional knowledge.

        Returns:
            str: The string representation of the current task state.
        """
        logger.info("[MetaAgent] Invoked view_task_state")
        res = ctx.deps.to_model_repr()
        logger.info(f"[MetaAgent] view_task_state result: {res}")
        return res

    @meta_agent.tool
    async def select_diff_from_diff_store(ctx: RunContext[TaskState], index:str) -> str: 
        """
        Select a diff (represented as a string) from the TaskState diff_store. 
        This tool is suitable to select a final patch to solve some tasks, or can be used to view intermediate results and compare candidates. 

        Args:
            index (str): the key of which element in the diff store to select.

        Returns:
            str: A string representation of a git diff originating fro mthe current TaskStates diff_store
        """
        diff_store = ctx.deps.diff_store
        logger.info(f"[MetaAgent] Invoced select_diff_from_diff_store tool with index {index} ({len(diff_store)} entries in diff_store)")
        if len(diff_store) == 0:
            raise ToolError("There are currently no diffs stored in the diff-store")
        if index not in diff_store.id_to_diff.keys():
            appendix = "" if len(diff_store) > 5 else "Available keys in diff_store: " + " ".join(diff_store.id_to_diff.keys())
            raise ToolError(f"Key {index} was not in the diff_store. {appendix}")
        else:
            return diff_store.id_to_diff[index]

    return meta_agent


def agent_loop(task_state: TaskState):
    """
    Main agent loop.
    """
    # first initialize some of the tools based on the task.
    init_bash_tool(
        task_state.task.get_working_directory(),
        command_transformer=task_state.task.command_transformer,
    )
    init_edit_tools(task_state.task.get_working_directory())
    meta_agent = init_agent()
    # actually running the agent
    result = meta_agent.run_sync("Invoke tools to complete the task.", deps=task_state)

    return result.output
