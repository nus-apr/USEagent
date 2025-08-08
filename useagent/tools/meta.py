import time

from loguru import logger
from pydantic_ai import RunContext

from useagent.config import ConfigSingleton
from useagent.pydantic_models.artifacts.git import DiffEntry, DiffStore
from useagent.pydantic_models.common.constrained_types import NonEmptyStr, PositiveInt
from useagent.pydantic_models.task_state import TaskState
from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ArgumentEntry, ToolErrorInfo
from useagent.tools.bash import get_bash_history


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
        time.sleep(0.25)
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
        time.sleep(0.25)
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
        time.sleep(0.25)
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
