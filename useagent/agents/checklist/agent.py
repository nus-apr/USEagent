from pathlib import Path

from loguru import logger
from pydantic_ai import Agent

import useagent.common.constants as constants
from useagent.common.context_window import fit_messages_into_context_window
from useagent.config import AppConfig, ConfigSingleton
from useagent.microagents.decorators import (
    alias_for_microagents,
    conditional_microagents_triggers,
)
from useagent.microagents.management import load_microagents_from_project_dir
from useagent.pydantic_models.info.checklist import CheckList
from useagent.pydantic_models.info.environment import Environment
from useagent.pydantic_models.task_state import TaskState

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()


@conditional_microagents_triggers(load_microagents_from_project_dir())
@alias_for_microagents("CHECKLIST")
def init_agent(config: AppConfig | None = None) -> Agent[None, CheckList]:
    if config is None:
        config = ConfigSingleton.config
    assert config is not None

    checklist_agent = Agent(
        config.model,
        instructions=SYSTEM_PROMPT,
        output_type=CheckList,
        retries=constants.CHECKLIST_AGENT_RETRIES,
        output_retries=constants.CHECKLIST_AGENT_OUTPUT_RETRIES,
        history_processors=[fit_messages_into_context_window],
    )

    @checklist_agent.instructions
    def add_output_description() -> str:
        return (
            f"""
        ---------------------------------------------------
        Output:

        You are expected to return a `{str(CheckList)}`.
        """
            + CheckList.get_output_instructions()
        )

    logger.debug("[ChecklistAgent] Initialized Checklist Agent")
    return checklist_agent


def construct_instructions(
    original_task: str,
    bash_history: list[str],
    task_state: TaskState,
    environment: Environment | None,
) -> str:
    instruction: str = f"""
        Your task is to fill a checklist regarding the project trajectory.
        You have the checklist in your `deps`, so you can fill it step by step.
        I will now present you with artifacts from the trajectory, and you inherit the message_history.
        Not all artifacts must be 100% accurate and might have been deprecated - but they are a fair source of information.
        Consider the information in the artifacts as correct, unless you see later messages or commands that contradict them.
        The original task (This should not affect the results of your checklist, but help to find focus points):
        {original_task}
        {'The environment that a probing agent identified: \n {str(environment)}' if environment else 'There was no dedicated `environment` information from probing.'}
        The full TaskState as seen last is: 
        {str(task_state)}
        The recent bash history:
        {'\n'.join(bash_history)}
    """
    return instruction
