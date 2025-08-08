## NOTE: implment MetaAgent with agent delegation

from pathlib import Path

from loguru import logger
from pydantic_ai import Agent, RunContext
from pydantic_ai.tools import Tool

from useagent.agents.edit_code.agent import init_agent as init_edit_code_agent
from useagent.agents.probing.agent import init_agent as init_probing_agent
from useagent.agents.search_code.agent import init_agent as init_search_code_agent
from useagent.agents.vcs.agent import init_agent as init_vcs_agent
from useagent.config import AppConfig, ConfigSingleton
from useagent.microagents.decorators import (
    alias_for_microagents,
    conditional_microagents_triggers,
)
from useagent.microagents.management import load_microagents_from_project_dir
from useagent.pydantic_models.artifacts.code import Location
from useagent.pydantic_models.artifacts.git import DiffEntry
from useagent.pydantic_models.info.environment import Environment
from useagent.pydantic_models.info.partial_environment import PartialEnvironment
from useagent.pydantic_models.task_state import TaskState
from useagent.state.usage_tracker import UsageTracker
from useagent.tools.bash import init_bash_tool
from useagent.tools.edit import init_edit_tools
from useagent.tools.meta import (
    remove_diffs_from_diff_store,
    select_diff_from_diff_store,
    view_task_state,
)

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()
# TODO: define the output type

USAGE_TRACKER = UsageTracker()


@conditional_microagents_triggers(load_microagents_from_project_dir())
@alias_for_microagents("META")
def init_agent(config: AppConfig | None = None) -> Agent[TaskState, str]:
    if config is None:
        config = ConfigSingleton.config
    assert config is not None

    meta_agent = Agent(
        config.model,
        instructions=SYSTEM_PROMPT,
        deps_type=TaskState,
        retries=3,
        output_retries=5,
        tools=[
            Tool(select_diff_from_diff_store, takes_ctx=True, max_retries=3),
            Tool(view_task_state, takes_ctx=True, max_retries=0),
            Tool(remove_diffs_from_diff_store, takes_ctx=True, max_retries=5),
        ],
        output_type=str,
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

    @meta_agent.tool(retries=5)
    async def probe_environment(ctx: RunContext[TaskState]) -> Environment:
        """Investigate the currently active environment relevant to the project.

        This is a tool very relevant if you
            - start a new task
            - received a lot of errors related to project structure
            - received a lot of errors related to commands and command arguments
            - perceived errors related to permission
            - switched environments
            - altered the environment, e.g. by performing installations

        This action can be considered safe, but you might want to avoid calling it too often in favour of costs.

        Returns:
            Environment: Currently active environment, as detected by the sub-agent.

        As a side effect, the current environment in the TaskState will be set to the newly obtained one.
        """
        logger.info("[MetaAgent] Invoked probe_environment")

        probing_agent = init_probing_agent()
        environment_under_construction: PartialEnvironment = PartialEnvironment()
        probing_agent_result = await probing_agent.run(
            deps=environment_under_construction
        )
        env: Environment = probing_agent_result.output
        next_id: int = len(ctx.deps.known_environments.keys())

        logger.info(f"[ProbingAgent] identified {env}")
        logger.debug(
            f"[MetaAgent] Probing finished for {env.project_root} @ {env.git_status.active_git_commit} (Stored as {'env_'+str(next_id)})"
        )
        ctx.deps.active_environment = env
        ctx.deps.known_environments["env_" + str(next_id)] = env

        USAGE_TRACKER.add(probing_agent.name, probing_agent_result.usage())

        return env

    @meta_agent.tool(retries=6)
    async def search_code(
        ctx: RunContext[TaskState], instruction: str
    ) -> list[Location]:
        """Search for relevant locations in the codebase. Only search in source code files, not test files.

        Args:
            instruction (str): Comprehensive instruction for the search, including keywords, file types, and other criteria. Give as many details as possible to improve the search results.

        Returns:
            list[Location]: List of locations in the codebase that match the search criteria.
        """
        logger.info(f"[MetaAgent] Invoked search_code with instruction: {instruction}")
        search_code_agent = init_search_code_agent()
        search_code_agent_result = await search_code_agent.run(
            instruction, deps=ctx.deps
        )
        locations = search_code_agent_result.output
        logger.info(f"[MetaAgent] search_code result: {locations}")

        # update task state with the found code locations
        ctx.deps.code_locations.extend(locations)

        USAGE_TRACKER.add(search_code_agent.name, search_code_agent_result.usage())
        return locations

    @meta_agent.tool(retries=4)
    async def edit_code(
        ctx: RunContext[TaskState], instruction: str
    ) -> DiffEntry | None:
        """Edit the codebase based on the provided instruction.

        Args:
            instruction (str): Instruction for the code edit. The instrution should be very specific, typically should include where in the codebase to edit (files, lines, etc.), what to change, and how to change it.

        Returns:
            DiffEntry: A unified diff of the changes that can be applied to the codebase.
        """
        logger.info(f"[MetaAgent] Invoked edit_code with instruction: {instruction}")
        edit_code_agent = init_edit_code_agent()

        edit_result = await edit_code_agent.run(instruction, deps=ctx.deps)
        diff: DiffEntry = edit_result.output
        logger.info(f"[MetaAgent] edit_code result: {diff}")
        # update task state with the diff
        diff_id: str = ctx.deps.diff_store.add_entry(diff)
        logger.info(f"[MetaAgent] Added diff entry with ID: {diff_id}")
        USAGE_TRACKER.add(edit_code_agent.name, edit_result.usage())
        return diff

    @meta_agent.tool(retries=4)
    async def vcs(
        ctx: RunContext[TaskState], instruction: str
    ) -> DiffEntry | str | None:
        """Perform tasks related to version-management given the provided instruction.

        Args:
            instruction (str): Instruction for the version management. The instruction should be very specific, typically should include the expected outcome and whether or not a action should be performed. Pay special attention to describe the expected start and end state, if a change in the VCS is required.

        Returns:
            DiffEntry | str | None: A git-diff of the requested entry, a string answering a question or retrieving other information, or None in case the performed action did not need any return value.
        """
        logger.info(f"[MetaAgent] Invoked vcs_agent with instruction: {instruction}")
        vcs_agent = init_vcs_agent()

        vcs_result = await vcs_agent.run(instruction, deps=ctx.deps)

        match vcs_result.output:
            case DiffEntry():
                diff: DiffEntry = vcs_result.output
                logger.info(f"[MetaAgent] vcs_agent diff result: {diff}")
                # update task state with the diff
                diff_id: str = ctx.deps.diff_store.add_entry(diff)
                logger.debug(f"[MetaAgent] Added diff entry with ID: {diff_id}")
            case str():
                logger.info(
                    f"[MetaAgent] VCS-agent returned a string: {vcs_result.output}"
                )
            case None:
                logger.info("[MetaAgent] VCS-agent returned `None`")
        return vcs_result

    ### Action definitions END

    return meta_agent


def agent_loop(task_state: TaskState):
    """
    Main agent loop.
    """
    # first initialize some of the tools based on the task.
    init_bash_tool(
        str(task_state._task.get_working_directory()),
        command_transformer=task_state._task.command_transformer,
    )
    init_edit_tools(str(task_state._task.get_working_directory()))
    meta_agent = init_agent()
    # actually running the agent
    prompt = "Invoke tools to complete the task."
    result = meta_agent.run_sync(prompt, deps=task_state)
    USAGE_TRACKER.add(meta_agent.name, result.usage())
    return result.output, USAGE_TRACKER
