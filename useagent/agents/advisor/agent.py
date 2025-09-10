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

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()


@conditional_microagents_triggers(load_microagents_from_project_dir())
@alias_for_microagents("ADVISOR")
def init_agent(config: AppConfig | None = None) -> Agent:
    if config is None:
        config = ConfigSingleton.config
    assert config is not None

    advisor_agent = Agent(
        config.model,
        instructions=SYSTEM_PROMPT,
        output_type=str,
        retries=constants.ADVISOR_AGENT_RETRIES,
        output_retries=constants.ADVISOR_AGENT_OUTPUT_RETRIES,
        history_processors=[fit_messages_into_context_window],
    )

    logger.debug("[Advisor Agent] Initialized Advisor Agent")
    return advisor_agent
