from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.tools import Tool

import useagent.common.constants as constants
from useagent.common.context_window import fit_messages_into_context_window
from useagent.config import AppConfig, ConfigSingleton
from useagent.microagents.decorators import (
    alias_for_microagents,
    conditional_microagents_triggers,
)
from useagent.microagents.management import load_microagents_from_project_dir
from useagent.pydantic_models.artifacts.git.diff_store import DiffEntryKey
from useagent.pydantic_models.task_state import TaskState
from useagent.tools.edit import (
    create,
    insert,
    replace_file,
    str_replace,
    view,
)
from useagent.tools.git import extract_diff

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()


@conditional_microagents_triggers(load_microagents_from_project_dir())
@alias_for_microagents("EDIT")
def init_agent(
    config: AppConfig | None = None,
) -> Agent[TaskState, DiffEntryKey]:  # type: ignore
    if config is None:
        config = ConfigSingleton.config
    assert config is not None

    agent = Agent(
        config.model,
        instructions=SYSTEM_PROMPT,
        deps_type=TaskState,
        output_type=DiffEntryKey,  # type: ignore
        retries=constants.EDIT_CODE_AGENT_RETRIES,
        output_retries=constants.EDIT_CODE_AGENT_OUTPUT_RETRIES,
        tools=[
            Tool(view),
            Tool(create),
            Tool(str_replace),
            Tool(insert),
            Tool(extract_diff, takes_ctx=True),
            # TODO: Figure out how to make this work with SWE - we often see a patch as a full file rather than a delta.
            # Tool(read_file_as_diff, takes_ctx=True),
            Tool(replace_file),
        ],
        history_processors=[fit_messages_into_context_window],
    )

    @agent.instructions
    def add_instructions_on_git_diffs(self) -> str:
        return """
        You are tasked to create a git diff using the specified and relevant tools. 
        The relevant extraction tools will make a git diff for you, based on the file changes you made, and only return a reference to the diff. 

        Assume that your results cannot be merged or combined upstream - you must report a single diff that contains all changes at once.

        Pay special attention to the ToolErrors you might encounter, especially those that you see frequently. 
        You should never call `extract_diff` twice in a row (with the same parameters) as it will not result in a different result. 
        If you see any ToolError from these extraction tools, think deeply whether your available diffs are sufficient, or exactly which changes are necessary to create diffs closer to your instructions.
        """

    @agent.instructions
    def add_output_instructions(self) -> str:
        return """
        ------------------------------------------------
        Output:
        Your expected output is a `DiffEntryKey`. 
        After you called a method that extracts git diffs, a successful extraction will store the DiffEntry in your TaskState and return you a diff_entry. 
        A diffentry must match the pattern `diff_XXX` where XXX is a positive integer. 
        """

    return agent
