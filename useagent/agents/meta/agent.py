## NOTE: implment MetaAgent with agent delegation
from pathlib import Path
from typing import Literal

from loguru import logger
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelMessage
from pydantic_ai.tools import Tool
from pydantic_ai.usage import Usage, UsageLimits

from useagent.agents.edit_code.agent import init_agent as init_edit_code_agent
from useagent.agents.probing.agent import init_agent as init_probing_agent
from useagent.agents.search_code.agent import init_agent as init_search_code_agent
from useagent.agents.test_execution.agent import init_agent as init_test_execution_agent
from useagent.agents.vcs.agent import init_agent as init_vcs_agent
from useagent.config import AppConfig, ConfigSingleton
from useagent.microagents.decorators import (
    alias_for_microagents,
    conditional_microagents_triggers,
)
from useagent.microagents.management import load_microagents_from_project_dir
from useagent.pydantic_models.artifacts.code import Location
from useagent.pydantic_models.artifacts.git import DiffEntry
from useagent.pydantic_models.artifacts.test_result import TestResult
from useagent.pydantic_models.info.environment import (
    Commands,
    Environment,
    GitStatus,
    Package,
)
from useagent.pydantic_models.output.action import Action
from useagent.pydantic_models.output.answer import Answer
from useagent.pydantic_models.output.code_change import CodeChange
from useagent.pydantic_models.provides_output_instructions import (
    ProvidesOutputInstructions,
)
from useagent.pydantic_models.task_state import TaskState
from useagent.state.usage_tracker import UsageTracker
from useagent.tools.bash import init_bash_tool, make_bash_tool_for_agent
from useagent.tools.edit import init_edit_tools, read_file_as_diff
from useagent.tools.meta import (
    remove_diffs_from_diff_store,
    select_diff_from_diff_store,
    view_command_history,
    view_task_state,
)

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()

USAGE_TRACKER = UsageTracker()


async def summarize_old_messages(messages: list[ModelMessage]) -> list[ModelMessage]:
    # After hitting 100 messages, summarize the oldest 30
    MESSAGE_THRESHHOLD: int = 100
    SUMMARY_FRAME: int = 30
    if len(messages) > MESSAGE_THRESHHOLD:
        logger.info(
            f"[META] Summary triggered, summarizing oldest {SUMMARY_FRAME} messages"
        )
        summarize_agent = Agent(
            ConfigSingleton.config.model,
            instructions="""
        Summarize this conversation, omitting small talk and unrelated topics.
        Focus on the technical discussion, most relevant artifacts and next steps.
        Filter out noisy artifacts or information that is not relevant to the goals. 
        Summarize elements that have only been part from a `checklist` but have been successfully checked.
        """,
        )

        oldest_messages = messages[:SUMMARY_FRAME]
        summary = await summarize_agent.run(message_history=oldest_messages)
        USAGE_TRACKER.add("SUMMARIZER", summary.usage())
        logger.debug(
            f"[META] last {SUMMARY_FRAME} messages summarized as: \n {summary.new_messages()}"
        )
        # Return the last message and the summary
        return summary.new_messages() + messages[-1:]

    return messages


@conditional_microagents_triggers(load_microagents_from_project_dir())
@alias_for_microagents("META")
def init_agent(
    config: AppConfig | None = None,
    output_type: Literal[CodeChange, Answer, Action] = CodeChange,
) -> Agent[TaskState, CodeChange | Answer]:
    if config is None:
        config = ConfigSingleton.config
    assert config is not None

    meta_agent = Agent(
        config.model,
        instructions=SYSTEM_PROMPT,
        deps_type=TaskState,
        retries=3,
        output_retries=10,
        tools=[
            Tool(select_diff_from_diff_store, takes_ctx=True, max_retries=3),
            Tool(view_task_state, takes_ctx=True, max_retries=0),
            Tool(remove_diffs_from_diff_store, takes_ctx=True, max_retries=5),
            Tool(view_command_history, max_retries=2),
            Tool(
                make_bash_tool_for_agent("META", bash_call_delay_in_seconds=0.30),
                max_retries=4,
            ),
            Tool(read_file_as_diff),
        ],
        output_type=output_type,
        history_processors=[summarize_old_messages],
    )

    ## This adds the task description to instructions (SYSTEM prompt).
    @meta_agent.instructions
    def add_task_description(ctx: RunContext[TaskState]) -> str:
        """Add a task description to the TaskState.

        Args:
            task_description (str): The description of the task to be added.
        """
        return ctx.deps._task.get_issue_statement()

    ## Depending on the output type (if possible), describes the expected output format.
    @meta_agent.instructions
    def add_output_description() -> str:
        if isinstance(output_type, ProvidesOutputInstructions):
            logger.trace(
                f"[Setup] MetaAgent is expected to output a `{str(output_type)}`, adding output instructions."
            )
            return (
                f"""
            ---------------------------------------------------
            Output:

            You are expected to return a `{str(output_type)}`.
            """
                + output_type.get_output_instructions()
            )
        else:
            logger.warning(
                "[Setup] MetaAgent received a output type that did not implement the `get_output_instructions` method and will have less info."
            )
            return f"Output: You are expected to return a `{output_type}`"

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

        This action can be considered safe, but you might want to avoid calling it too often in favour of costs and runtime.

        Returns:
            Environment: Currently active environment, as detected by the sub-agent.

        As a side effect, the current environment in the TaskState will be set to the newly obtained one.
        """
        logger.info("[MetaAgent] Invoked probe_environment")

        logger.trace("[Probing Agent] Looking for Project root (Path)")
        path_probing_agent = init_probing_agent(output_type=Path, deps_type=None)
        path_probing_agent_result = await path_probing_agent.run(
            deps=None,
            usage_limits=UsageLimits(request_limit=35),
        )
        project_root = path_probing_agent_result.output

        logger.trace("[Probing Agent] Looking for Git Information")
        git_probing_agent = init_probing_agent(output_type=GitStatus, deps_type=None)
        git_probing_agent_result = await git_probing_agent.run(
            #    deps=starting_status,
            usage_limits=UsageLimits(request_limit=90),
        )
        git_status = git_probing_agent_result.output

        logger.trace("[Probing Agent] Looking for Important Commands")
        dep_commands = Commands(build_command='echo "TODO: Identify" && :')
        command_probing_agent = init_probing_agent(
            output_type=Commands, deps_type=Commands
        )
        command_probing_agent_result = await command_probing_agent.run(
            deps=dep_commands,
            usage_limits=UsageLimits(request_limit=115),
        )
        commands = command_probing_agent_result.output

        logger.trace("[Probing Agent] Looking for Packages")
        package_probing_agent = init_probing_agent(
            output_type=list[Package], deps_type=list[Package]
        )
        package_probing_agent_result = await package_probing_agent.run(
            deps=[],
            usage_limits=UsageLimits(request_limit=100),
        )
        packages = package_probing_agent_result.output

        env = Environment(
            project_root=project_root,
            git_status=git_status,
            commands=commands,
            packages=packages,
        )

        next_id: int = len(ctx.deps.known_environments.keys())

        logger.info(
            f"[MetaAgent] Probing finished for {env.project_root} @ {env.git_status.active_git_commit} (Stored as {'env_'+str(next_id)})"
        )
        ctx.deps.active_environment = env
        ctx.deps.known_environments["env_" + str(next_id)] = env

        probing_usage: Usage = (
            path_probing_agent_result.usage()
            + git_probing_agent_result.usage()
            + command_probing_agent_result.usage()
            + package_probing_agent_result.usage()
        )

        USAGE_TRACKER.add("PROBE", probing_usage)

        return env

    @meta_agent.tool(retries=3)
    async def execute_tests(ctx: RunContext[TaskState], instruction: str) -> TestResult:
        """Execute the projects tests or a subset of the tests.

        The required instructions should contain a detailed description of
        - The goal of the tests that you want to execute (i.e. what is it that you want to test)
        - any test files you already know to be relevant
        - whether you expect to need the whole test-suite, or only a subset
        - any code-locations that you want to be tested

        This test execution might be costly, so consider gathering information first on what to execute.

        Args:
            instruction (str): Comprehensive instruction for the test execution, including tests, files, test-goals, relevant locations. Give as many details as possible.

        Returns:
            TestResult: A summary of the executed tests and their output, as well as the actually executed command.
        """
        logger.info("[MetaAgent] Invoked execute_tests")
        logger.debug(f"[MetaAgent] Instructions to Execute Tests: {instruction}")

        test_agent = init_test_execution_agent()
        test_agent_output = await test_agent.run(
            instruction, deps=ctx.deps, usage_limits=UsageLimits(request_limit=115)
        )
        test_result: TestResult = test_agent_output.output

        logger.info(f"[Test Execution Agent] Tests resulted in {test_result}")

        USAGE_TRACKER.add(test_agent.name, test_agent_output.usage())
        # TODO: Also add a test-result lookup and storage? It should be relative to environment / git commit to be useful

        return test_result

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
            instruction, deps=ctx.deps, usage_limits=UsageLimits(request_limit=120)
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

        edit_result = await edit_code_agent.run(
            instruction, deps=ctx.deps, usage_limits=UsageLimits(request_limit=125)
        )
        diff: DiffEntry = edit_result.output
        logger.info(f"[MetaAgent] edit_code result: {diff}")
        # update task state with the diff
        try:
            diff_id: str = ctx.deps.diff_store.add_entry(diff)
            logger.info(f"[MetaAgent] Added diff entry with ID: {diff_id}")
        except ValueError as verr:
            if "diff already exists" in str(verr):
                logger.warning(
                    "[MetaAgent] Edit-Code Agent returned a (already known) diff towards the meta-agent"
                )
                existing_diff_id = (ctx.deps.diff_store.diff_to_id())[diff.diff_content]
                raise ValueError(
                    f"The edit-code agent returned a diff identical to an existing diff_id {existing_diff_id}. Reconsider your instructions or revisit the existing diff_id {existing_diff_id}."
                )
            else:
                raise verr
        finally:
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
        USAGE_TRACKER.add(vcs_agent.name, vcs_result.usage())
        return vcs_result.output

    ### Action definitions END

    return meta_agent


def agent_loop(
    task_state: TaskState, output_type: Literal[CodeChange, Answer, Action] = CodeChange
):
    """
    Main agent loop.
    """
    # first initialize some of the tools based on the task.
    init_bash_tool(
        str(task_state._task.get_working_directory()),
        command_transformer=task_state._task.command_transformer,
    )
    init_edit_tools(str(task_state._task.get_working_directory()))
    meta_agent = init_agent(output_type=output_type)
    # actually running the agent
    prompt = "Invoke tools to complete the task."
    result = meta_agent.run_sync(
        prompt, deps=task_state, usage_limits=UsageLimits(request_limit=100)
    )

    if (
        ConfigSingleton.is_initialized()
        and ConfigSingleton.config.optimization_toggles["reiterate-on-doubts"]
    ):
        if result.output and result.output.doubts:
            try:
                # TODO: store the result? To have something in case of timeout?
                # TODO: Add checking of usage // storing temporary usage.
                logger.info(
                    f"Initial attempt at repairing the task resulting in a result with doubts: {result.doubts}. Attempting to resolve doubts with changes"
                )
                logger.debug(f"Doubtful result was: {result}")
                new_instruction: str = (
                    f"While addressing the task, you produced a result that had the following doubts: {result.doubts}. Try to address your own doubts making changes to your result, or by identifying more information, with the tools at your disposal."
                )
                result = meta_agent.run_sync(
                    new_instruction,
                    deps=task_state,
                    usage_limits=UsageLimits(request_limit=75),
                )
            except Exception as exc:
                logger.error(
                    f"Error while re-iterating the result after doubts. Re-using previous, initial result (with doubts). Exception was: {exc}"
                )
        else:
            logger.debug("Task was finished without any doubts.")

    if output_type is CodeChange:
        diff_id = result.output.diff_id
        logger.info(f"Resolving {diff_id} in DiffStore:")
        try:
            diff_content = task_state.diff_store.id_to_diff[diff_id]
            logger.info(f"{diff_content}")
        except Exception as e:
            logger.error(f"Issue finding {diff_id} in DiffStore")
            logger.error(e)

    USAGE_TRACKER.add(meta_agent.name, result.usage())
    return result.output, USAGE_TRACKER
