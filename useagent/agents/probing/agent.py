from pathlib import Path

from loguru import logger
from pydantic_ai import Agent
from pydantic_ai.tools import Tool

from useagent.config import AppConfig, ConfigSingleton
from useagent.microagents.decorators import (
    alias_for_microagents,
    conditional_microagents_triggers,
)
from useagent.microagents.management import load_microagents_from_project_dir
from useagent.pydantic_models.info.environment import Commands, Package
from useagent.pydantic_models.provides_output_instructions import (
    ProvidesOutputInstructions,
)
from useagent.tools.bash import make_bash_tool_for_agent

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()


@conditional_microagents_triggers(load_microagents_from_project_dir())
@alias_for_microagents("PROBE")
def init_agent(output_type, config: AppConfig | None = None, deps_type=None) -> Agent:
    # DevNote (See Issue #17):
    # We had two previous attempts:
    # (1) Produce a full environment at once --- failed because task is too large
    # (2) Produce a partial environment, fill up, combine into larger environment --- failed because deps was not used properly. No fields filled.
    # Now the approach is to split up the probing-agent calls for the different environment parts,
    # each run reporting a different aspect, and after successful search merge them upstream in the USEAgent.
    # This means potentially high costs / calls, but all other attempts seemed to regularly fail.

    if config is None:
        config = ConfigSingleton.config
    assert config is not None

    if output_type is None:
        logger.error("[Probing Agent] Recieved no Output Type - aborting")
        raise ValueError("Unsupported Output_Type None received for init_agent")

    environment_probing_agent = Agent(
        config.model,
        instructions=SYSTEM_PROMPT,
        deps_type=deps_type,  # type: ignore
        output_type=output_type,
        retries=2,
        output_retries=3,
        tools=[
            Tool(
                make_bash_tool_for_agent("PROBE", bash_call_delay_in_seconds=0.35),
                max_retries=4,
            ),
        ],
    )

    logger.debug(
        f"[Probing Agent] Initialized basic Probing Agent for output {str(output_type)} with deps-type {str(deps_type)}"
    )

    @environment_probing_agent.instructions
    def defuse_probing_strictness() -> str:
        # The probing agent sometimes just considers the given Microagent options as a form of checklist.
        # This leads to it trying all possible commands, instead of aborting and continuing after a good find.
        if (
            ConfigSingleton.is_initialized()
            and ConfigSingleton.config.optimization_toggles[
                "loosen-probing-agent-strictness"
            ]
            and output_type is Commands
        ):
            return """
            Be considerate in how much probing you will do. 
            Do not treat commands that you know or have been presented with as a `checklist` that you have to fully investigate. 
            The chance that a project has multiple build or test commands is very unlikely, so after you have identified (and verified) a command continue to investigate other aspects.
            Unless you see it especially specified in e.g. a README or toml, you can assume the project does not contain a linting command.
            """
        return ""  # Toggle is off, do nothing.

    @environment_probing_agent.instructions
    def add_output_description(self) -> str:
        if output_type is Path:
            return "You are supposed to return a pathlib.Path that specifies the projects root."
        if output_type is list[Package] or "package" in str(output_type):
            return (
                "You are supposed to find packages installed on the system and the development environment. These are meant to be available in path or by common package managers, and not file-based. \n"
                + Package.get_output_instructions()
            )
        if isinstance(output_type, ProvidesOutputInstructions):
            return (
                """
            -----------
            Output:
            """
                + "\n"
                + output_type.get_output_instructions()
            )
        else:
            logger.warning(
                f"[Agent] Probing Agent received an output type that does not provide a `get_output_instructions`: {str(output_type)}"
            )
        return ""

    return environment_probing_agent
