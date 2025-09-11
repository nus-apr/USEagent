import time
from pathlib import Path

from loguru import logger
from pydantic_ai import RunContext
from pydantic_ai.messages import ModelMessage
from pydantic_ai.usage import Usage, UsageLimits

import useagent.common.constants as constants
from useagent.agents.advisor.agent import init_agent as init_advisor_agent
from useagent.agents.checklist.agent import (
    construct_instructions as construct_checklist_instructions,
)
from useagent.agents.checklist.agent import init_agent as init_checklist_agent
from useagent.agents.edit_code.agent import init_agent as init_edit_code_agent
from useagent.agents.probing.agent import init_agent as init_probing_agent
from useagent.agents.search_code.agent import init_agent as init_search_code_agent
from useagent.agents.test_execution.agent import init_agent as init_test_execution_agent
from useagent.agents.vcs.agent import init_agent as init_vcs_agent
from useagent.config import ConfigSingleton
from useagent.pydantic_models.artifacts.code import Location
from useagent.pydantic_models.artifacts.git import DiffEntry, DiffStore
from useagent.pydantic_models.artifacts.test_result import TestResult
from useagent.pydantic_models.common.constrained_types import NonEmptyStr, PositiveInt
from useagent.pydantic_models.info.checklist import CheckList
from useagent.pydantic_models.info.environment import (
    Commands,
    Environment,
    GitStatus,
    Package,
)
from useagent.pydantic_models.task_state import TaskState
from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ArgumentEntry, ToolErrorInfo
from useagent.state.usage_tracker import UsageTracker
from useagent.tools.bash import get_bash_history

USAGE_TRACKER: UsageTracker


def _set_usage_tracker(tracker: UsageTracker) -> None:
    # Small helper to avoid circular imports.
    # We pass the tracker as a reference, so if the agents here write into it, its shared.
    global USAGE_TRACKER
    USAGE_TRACKER = tracker


# ===================================================================
#             Meta-Information Retrieval & Interaction
#    (Non Agentic Interaction with e.g. Task-State or Bash History)
# ===================================================================


def select_diff_from_diff_store(
    ctx: RunContext[TaskState], diff_store_key: str
) -> str | ToolErrorInfo:
    """
    Select a diff (represented as a string) from the TaskState diff_store.
    This tool is suitable to select a final patch to solve some tasks, or can be used to view intermediate results and compare candidates.

    Args:
        diff_store_key (str): the key of which element in the diff store to select.

    Returns:
        str: A string representation of a git diff originating fro mthe current TaskStates diff_store
    """
    if (
        ConfigSingleton.is_initialized()
        and ConfigSingleton.config.optimization_toggles["meta-agent-speed-bumps"]
    ):
        time.sleep(constants.DIFF_STORE_INTERACTION_DELAY)
    diff_store = ctx.deps.diff_store
    return _select_diff_from_diff_store(diff_store, diff_store_key)


def remove_diffs_from_diff_store(
    ctx: RunContext[TaskState], keys_of_diffs_to_remove: list[str]
) -> DiffStore | ToolErrorInfo:
    """
    Remove all given diffs from the Diff Store.
    This action can be used if there are many partial diffs that are no longer relevant,
    if some diffs are known to be faulty / malformed or to keep only the most promising diffs in a growing diffstore.
    The result will be the newly constructed DiffStore without the specified elements, which will have new keys in place.

    Args:
        keys_of_diffs_to_remove (List[str]): The keys of which diffs to remove. Must be valid keys for elements in the diff-store.

    Returns:
        DiffStore: The updated DiffStore - The TaskStates' field will also be updated as a side-effect.
    """
    if (
        ConfigSingleton.is_initialized()
        and ConfigSingleton.config.optimization_toggles["meta-agent-speed-bumps"]
    ):
        time.sleep(constants.DIFF_STORE_INTERACTION_DELAY)
    diff_store = ctx.deps.diff_store
    result = _remove_diffs_from_diff_store(diff_store, keys_of_diffs_to_remove)
    if isinstance(result, DiffStore):
        logger.debug(
            f"Overwritting existing diffstore ({len(diff_store)} entries) with new diffstore ({len(result)} entries)"
        )
        ctx.deps.diff_store = result
    return result


def _remove_diffs_from_diff_store(
    diff_store: DiffStore, keys_of_diffs_to_remove: list[str]
) -> DiffStore | ToolErrorInfo:
    logger.info(
        f"[Tool] Invoked remove_diffs_from_diff_store tool removing {keys_of_diffs_to_remove}"
    )
    if not keys_of_diffs_to_remove:
        return ToolErrorInfo(message="Supplied no keys to remove.")
    for key in keys_of_diffs_to_remove:
        if not key.startswith("diff_"):
            return ToolErrorInfo(
                message=f"Supplied at least one key ({key}) that does not match the required format 'diff_X'",
                supplied_arguments=[
                    ArgumentEntry(
                        "keys_of_diffs_to_remove", str(keys_of_diffs_to_remove)
                    )
                ],
            )
        if key not in diff_store.id_to_diff.keys():
            return ToolErrorInfo(
                message=f"Supplied at least one key ({key}) that is not in the existing DiffStore",
                supplied_arguments=[
                    ArgumentEntry(
                        "keys_of_diffs_to_remove", str(keys_of_diffs_to_remove)
                    )
                ],
            )

    diffs_to_keep = [
        k for k in diff_store.id_to_diff.keys() if k not in keys_of_diffs_to_remove
    ]
    new_diff_store: DiffStore = DiffStore()
    for diff_to_keep in diffs_to_keep:
        new_diff_store.add_entry(diff_store.id_to_diff[diff_to_keep])

    return new_diff_store


def _select_diff_from_diff_store(
    diff_store: DiffStore, index: str
) -> str | ToolErrorInfo:
    logger.info(
        f"[Tool] Invoked select_diff_from_diff_store tool with index {index} ({len(diff_store)} entries in diff_store [{','.join(list(diff_store.id_to_diff.keys())[:8])}])"
    )
    if len(diff_store) == 0:
        return ToolErrorInfo(
            message="There are currently no diffs stored in the diff-store",
            supplied_arguments=[
                ArgumentEntry("diff_store", str(diff_store)),
                ArgumentEntry("index", str(index)),
            ],
        )
    # DevNote: Let's help a little if we got an integer
    if index.isdigit() and int(index) >= 0:
        index = "diff_" + index
    if index not in diff_store.id_to_diff.keys():
        logger.debug(
            f"[Tool] poor key-choice: {index} was tried to select but does not exist [{','.join(list(diff_store.id_to_diff.keys())[:8])}]"
        )
        appendix = "Available keys in diff_store: " + " ".join(
            list(diff_store.id_to_diff.keys())[:8]
        )
        return ToolErrorInfo(
            message=f"Key {index} was not in the diff_store. {appendix}",
            supplied_arguments=[
                ArgumentEntry("diff_store", str(diff_store)),
                ArgumentEntry("index", str(index)),
            ],
        )
    else:
        entry: DiffEntry = diff_store.id_to_diff[index]
        if not entry.diff_content or not (entry.diff_content.strip()):
            logger.warning("[Tool] An empty diff was selected by the agent.")
        return entry.diff_content


def view_task_state(ctx: RunContext[TaskState]) -> str:
    """View the current task state.
    Use this tool to retrieve the up-to-date task state, including code locations, test locations, the diff store, and additional knowledge.

    Returns:
        str: The string representation of the current task state.
    """
    if (
        ConfigSingleton.is_initialized()
        and ConfigSingleton.config.optimization_toggles["meta-agent-speed-bumps"]
    ):
        time.sleep(constants.DIFF_STORE_INTERACTION_DELAY)
    logger.info("[Tool] Invoked view_task_state")
    res = ctx.deps.to_model_repr()
    logger.debug(f"[Tool] view_task_state result: {res}")
    return res


def view_command_history(
    limit: PositiveInt = 5,
) -> list[tuple[NonEmptyStr, NonEmptyStr, CLIResult | ToolErrorInfo | Exception]]:
    """
    Inspect the recently used commands and their outputs.
    Can be an empty list, in case you have not used any agent that uses any commandline.

    Args:
        limit (PositiveInt): additional limitation to the last `limit` entries, default: last 5.
    Returns:
        list(Tuple[str,str,CLIResult | ToolErrorInfo | Exception]): A list of (utmost) the last 50 commands used and their output.
    """
    return list(get_bash_history())[-limit:]


# ===================================================================
#                      Agent-Agent Calls
#           (complex tools that wrap other agents)
# ===================================================================


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
        usage_limits=UsageLimits(
            request_limit=constants.PROBING_AGENT_WORKDIR_REQUEST_LIMIT
        ),
    )
    project_root = path_probing_agent_result.output

    logger.trace("[Probing Agent] Looking for Git Information")
    git_probing_agent = init_probing_agent(output_type=GitStatus, deps_type=None)
    git_probing_agent_result = await git_probing_agent.run(
        #    deps=starting_status,
        usage_limits=UsageLimits(
            request_limit=constants.PROBING_AGENT_GIT_REQUEST_LIMIT
        ),
    )
    git_status = git_probing_agent_result.output

    logger.trace("[Probing Agent] Looking for Important Commands")
    dep_commands = Commands(build_command='echo "TODO: Identify" && :')
    command_probing_agent = init_probing_agent(output_type=Commands, deps_type=Commands)
    command_probing_agent_result = await command_probing_agent.run(
        deps=dep_commands,
        usage_limits=UsageLimits(
            request_limit=constants.PROBING_AGENT_COMMAND_REQUEST_LIMIT
        ),
    )
    commands = command_probing_agent_result.output

    logger.trace("[Probing Agent] Looking for Packages")
    package_probing_agent = init_probing_agent(
        output_type=list[Package], deps_type=list[Package]
    )
    package_probing_agent_result = await package_probing_agent.run(
        deps=[],
        usage_limits=UsageLimits(
            request_limit=constants.PROBING_AGENT_PACKAGE_REQUEST_LIMIT
        ),
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
        instruction,
        deps=ctx.deps,
        usage_limits=UsageLimits(
            request_limit=constants.EXECUTE_TESTS_AGENT_REQUEST_LIMIT
        ),
    )
    test_result: TestResult = test_agent_output.output

    logger.info(f"[Test Execution Agent] Tests resulted in {test_result}")

    USAGE_TRACKER.add(test_agent.name, test_agent_output.usage())
    # TODO: Also add a test-result lookup and storage? It should be relative to environment / git commit to be useful

    return test_result


async def search_code(ctx: RunContext[TaskState], instruction: str) -> list[Location]:
    """Search for relevant locations in the codebase. Only search in source code files, not test files.

    Args:
        instruction (str): Comprehensive instruction for the search, including keywords, file types, and other criteria. Give as many details as possible to improve the search results.

    Returns:
        list[Location]: List of locations in the codebase that match the search criteria.
    """
    logger.info(f"[MetaAgent] Invoked search_code with instruction: {instruction}")
    search_code_agent = init_search_code_agent()
    search_code_agent_result = await search_code_agent.run(
        instruction,
        deps=ctx.deps,
        usage_limits=UsageLimits(request_limit=constants.SEARCH_AGENT_REQUEST_LIMIT),
    )
    locations = search_code_agent_result.output
    logger.info(f"[MetaAgent] search_code result: {locations}")

    # update task state with the found code locations
    ctx.deps.code_locations.extend(locations)

    USAGE_TRACKER.add(search_code_agent.name, search_code_agent_result.usage())
    return locations


async def edit_code(ctx: RunContext[TaskState], instruction: str) -> DiffEntry | None:
    """Edit the codebase based on the provided instruction.

    To invoke the EditCode tool, think step by step:
        1. What kind of new edit is needed?
        2. Are you going to make new edit to fix previous wrong/incomplete edits? If yes, you should supply the diff_id of these previous edits in the `pre_patches` argument.
        Note that you should include a diff_id even if it contains error, because it can be useful to use it as a reference.
        3. After deciding on what should be supplied as `pre_patches`, think about what kind of changes should be made on top of them and describe that in the `instructions` argument.

    Args:
        instruction (str): Instruction for the code edit. The instrution should be very specific, typically should include where in the codebase to edit (files, lines, etc.), what to change, and how to change it.

    Returns:
        DiffEntry: A unified diff of the changes that can be applied to the codebase.
    """
    logger.info(f"[MetaAgent] Invoked edit_code with instruction: {instruction}")
    edit_code_agent = init_edit_code_agent()

    edit_result = await edit_code_agent.run(
        instruction,
        deps=ctx.deps,
        usage_limits=UsageLimits(request_limit=constants.EDIT_CODE_AGENT_REQUEST_LIMIT),
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


async def vcs(ctx: RunContext[TaskState], instruction: str) -> DiffEntry | str | None:
    """Perform tasks related to version-management given the provided instruction.

    Args:
        instruction (str): Instruction for the version management. The instruction should be very specific, typically should include the expected outcome and whether or not a action should be performed. Pay special attention to describe the expected start and end state, if a change in the VCS is required.

    Returns:
        DiffEntry | str | None: A git-diff of the requested entry, a string answering a question or retrieving other information, or None in case the performed action did not need any return value.
    """
    logger.info(f"[MetaAgent] Invoked vcs_agent with instruction: {instruction}")
    vcs_agent = init_vcs_agent()

    vcs_result = await vcs_agent.run(
        instruction,
        deps=ctx.deps,
        usage_limits=UsageLimits(request_limit=constants.VCS_AGENT_REQUEST_LIMIT),
    )

    match vcs_result.output:
        case DiffEntry():
            diff: DiffEntry = vcs_result.output
            logger.info(f"[MetaAgent] vcs_agent diff result: {diff}")
            # update task state with the diff
            try:
                diff_id: str = ctx.deps.diff_store.add_entry(diff)
                logger.debug(f"[MetaAgent] Added diff entry with ID: {diff_id}")
            except ValueError as verr:
                if "diff already exists" in str(verr):
                    logger.warning(
                        "[MetaAgent] VCS Agent returned a (already known) diff towards the meta-agent"
                    )
                # TODO: Do we want to add something more here than logging?
        case str():
            logger.info(f"[MetaAgent] VCS-agent returned a string: {vcs_result.output}")
        case None:
            logger.info("[MetaAgent] VCS-agent returned `None`")
    USAGE_TRACKER.add(vcs_agent.name, vcs_result.usage())
    return vcs_result.output


# ==========================================================================
#                             Non-Tool Agent Calls
#    (We call agents in the broader logic, but not provide them as tools)
# ==========================================================================


def advising_on_doubts(
    artifact: str,
    doubts: str,
    task_desc: str,
    cmd_history: list[str],
    message_history: list[ModelMessage] | None = None,
) -> NonEmptyStr:
    instructions = (
        f"The user was given this task:\n{task_desc}\n For which you created {artifact} \nThere are doubts remaining about this:\n{doubts}\n"
        f"For your judgement, also consider the existing message history. The provided message history might have been shortened to only the newest messages."
        f"These were the last executed commands and their results:"
        "\n".join(cmd_history)
    )

    advisor_agent = init_advisor_agent()
    advise_result = advisor_agent.run_sync(
        instructions,
        message_history=message_history,
        usage_limits=UsageLimits(request_limit=constants.ADVISOR_AGENT_REQUEST_LIMIT),
    )
    logger.debug(f"[Meta] Advice received from Advisor Agent: {advise_result.output}")
    USAGE_TRACKER.add(advisor_agent.name, advise_result.usage())
    return advise_result.output


def _gather_checklist(
    task_instruction: str,
    task_state: TaskState,
    cmd_history: list[str],
    environment: Environment | None,
    message_history: list[ModelMessage] | None = None,
) -> CheckList:
    logger.debug("[Meta] Asking for CheckList")
    instructions = construct_checklist_instructions(
        original_task=task_instruction,
        bash_history=cmd_history,
        task_state=task_state,
        environment=environment,
    )

    checklist_agent = init_checklist_agent()
    empty_checklist: CheckList = CheckList()

    checklist_result = checklist_agent.run_sync(
        instructions,
        deps=empty_checklist,
        usage_limits=UsageLimits(request_limit=constants.CHECKLIST_AGENT_REQUEST_LIMIT),
        message_history=message_history,
    )
    logger.debug(f"[Meta] CheckList result: {checklist_result.output}")
    USAGE_TRACKER.add(checklist_agent.name, checklist_result.usage())
    return checklist_result.output
