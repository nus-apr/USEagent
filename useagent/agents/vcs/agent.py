from pathlib import Path
from typing import Union

from pydantic_ai import Agent
from pydantic_ai.tools import Tool

from useagent.common.context_window import fit_messages_into_context_window
from useagent.config import AppConfig, ConfigSingleton
from useagent.microagents.decorators import (
    alias_for_microagents,
    conditional_microagents_triggers,
)
from useagent.microagents.management import load_microagents_from_project_dir
from useagent.pydantic_models.artifacts.git import DiffEntry
from useagent.pydantic_models.task_state import TaskState
from useagent.tools.bash import make_bash_tool_for_agent
from useagent.tools.git import (
    check_for_merge_conflict_markers,
    extract_diff,
    find_merge_conflicts,
    view_commit_as_diff,
)
from useagent.tools.meta import select_diff_from_diff_store, view_task_state

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()


@conditional_microagents_triggers(load_microagents_from_project_dir())
@alias_for_microagents("VCS")
def init_agent(
    config: AppConfig | None = None,
) -> Agent[TaskState, DiffEntry | str]:
    # Dev Note (See #27 too), we first had DiffEntry | str | None as output,
    # But imo returning None is not good, it should at least give a short message as a `str`.
    if config is None:
        config = ConfigSingleton.config
    assert config is not None

    agent = Agent(
        config.model,
        instructions=SYSTEM_PROMPT,
        deps_type=TaskState,
        output_type=Union[DiffEntry, str],
        retries=2,
        output_retries=5,
        tools=[
            Tool(
                make_bash_tool_for_agent("VCS", bash_call_delay_in_seconds=0.25),
                max_retries=3,
            ),
            Tool(view_commit_as_diff),
            Tool(find_merge_conflicts),
            Tool(check_for_merge_conflict_markers),
            Tool(extract_diff),
            Tool(select_diff_from_diff_store, takes_ctx=True, max_retries=3),
            Tool(view_task_state, takes_ctx=True),
        ],
        history_processors=[fit_messages_into_context_window],
    )

    @agent.instructions
    def add_optional_answer_instructions() -> str:
        if (
            ConfigSingleton.is_initialized()
            and ConfigSingleton.config.optimization_toggles[
                "vcs-agent-answer-instructions"
            ]
        ):
            return """
            If you are uncertain whether the task can be achieved by tooling, respond with a `str` outlining your reasoning for rejection. 
            Try to solve the task with your other available tools first, and do not report an early rejection. 

            Once you consider a rejection, formulate what information or steps are necessary to solve the instruction you are given, or any reason why it can never be achieved. 
            """
        else:
            return ""

    return agent
