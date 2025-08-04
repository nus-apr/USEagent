from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.tools import Tool

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

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()


@conditional_microagents_triggers(load_microagents_from_project_dir())
@alias_for_microagents("VCS")
def init_agent(
    config: AppConfig | None = None,
) -> Agent[TaskState, DiffEntry | str | None]:
    if config is None:
        config = ConfigSingleton.config
    assert config is not None

    agent = Agent(
        config.model,
        instructions=SYSTEM_PROMPT,
        deps_type=TaskState,
        output_type=DiffEntry,
        tools=[
            Tool(make_bash_tool_for_agent("VCS"), max_retries=4),
            Tool(view_commit_as_diff),
            Tool(find_merge_conflicts),
            Tool(check_for_merge_conflict_markers),
            Tool(extract_diff),
        ],
    )
    return agent
