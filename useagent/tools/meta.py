from loguru import logger
from pydantic_ai import RunContext

from useagent.pydantic_models.git import DiffEntry, DiffStore
from useagent.pydantic_models.task_state import TaskState
from useagent.tools.base import ToolError


def select_diff_from_diff_store(ctx: RunContext[TaskState], diff_store_key: str) -> str:
    """
    Select a diff (represented as a string) from the TaskState diff_store.
    This tool is suitable to select a final patch to solve some tasks, or can be used to view intermediate results and compare candidates.

    Args:
        diff_store_key (str): the key of which element in the diff store to select.

    Returns:
        str: A string representation of a git diff originating fro mthe current TaskStates diff_store
    """
    diff_store = ctx.deps.diff_store
    return _select_diff_from_diff_store(diff_store, diff_store_key)


def _select_diff_from_diff_store(diff_store: DiffStore, index: str) -> str:
    logger.info(
        f"[Tool] Invoked select_diff_from_diff_store tool with index {index} ({len(diff_store)} entries in diff_store)"
    )
    if len(diff_store) == 0:
        raise ToolError("There are currently no diffs stored in the diff-store")
    # DevNote: Let's help a little if we got an integer
    if index.isdigit() and int(index) >= 0:
        index = "diff_" + index
    if index not in diff_store.id_to_diff.keys():
        logger.debug(
            f"[Tool] poor key-choice: {index} was tried to select but does not exist [{",".join(list(diff_store.id_to_diff.keys())[:8])}]"
        )
        appendix = "Available keys in diff_store: " + " ".join(
            list(diff_store.id_to_diff.keys())[:8]
        )
        raise ToolError(f"Key {index} was not in the diff_store. {appendix}")
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
    logger.info("[Tool] Invoked view_task_state")
    res = ctx.deps.to_model_repr()
    logger.debug(f"[Tool] view_task_state result: {res}")
    return res
