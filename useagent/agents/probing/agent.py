from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.tools import Tool

from useagent.config import AppConfig, ConfigSingleton
from useagent.microagents.decorators import (
    alias_for_microagents,
    conditional_microagents_triggers,
)
from useagent.microagents.management import load_microagents_from_project_dir
from useagent.pydantic_models.info.environment import Environment
from useagent.pydantic_models.info.partial_environment import PartialEnvironment
from useagent.tools.bash import make_bash_tool_for_agent
from useagent.tools.probing import check_environment, report_environment

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()


@conditional_microagents_triggers(load_microagents_from_project_dir())
@alias_for_microagents("PROBE")
def init_agent(
    config: AppConfig | None = None,
) -> Agent[PartialEnvironment, Environment]:

    if config is None:
        config = ConfigSingleton.config
    assert config is not None

    # DevNote:
    # Initially, the probing agent was just meant to return a `Environment` using Bash,
    # but that is too difficult for the agent without doing it `step by step`.
    # To support this incremental building, we introduced a PartialEnvironment that is stored in the deps.
    # It can be checked and transformed with a little tool.
    # Just using the Environment for incremental building, because that requires a mutable element,
    # Which might lead to consistency issues (i.e. at the moment a environment is a clear tuple that is collected together at one point of time.)

    environment_probing_agent = Agent(
        config.model,
        instructions=SYSTEM_PROMPT,
        deps_type=PartialEnvironment,
        output_type=Environment,
        retries=2,
        output_retries=5,
        tools=[
            Tool(
                make_bash_tool_for_agent("PROBE", bash_call_delay_in_seconds=0.2),
                max_retries=5,
            ),
            Tool(report_environment, takes_ctx=True, max_retries=2),
            Tool(check_environment, takes_ctx=True, max_retries=1),
        ],
    )

    @environment_probing_agent.instructions
    def stress_partial_environment() -> str:
        # The Probing Agent was struggling to build the partial environment,
        # largely due to it's complexity.
        if (
            ConfigSingleton.is_initialized()
            and ConfigSingleton.config.optimization_toggles[
                "stress-probing-agent-partial-environment"
            ]
        ):
            return """
            The task you are facing is quite elaborate and I want you to report a lot of details. 

            You can get feedback on the missing fields in your PartialEnvironment using the `check_environment` tool.
            You can formulate your final answers using the `report_environment` tool, 
            but NEVER use this without first considering the response from `check_environment` tool. 
            """
        return ""  # Toggle is off, do nothing

    @environment_probing_agent.instructions
    def defuse_probing_strictness() -> str:
        # The probing agent sometimes just considers the given Microagent options as a form of checklist.
        # This leads to it trying all possible commands, instead of aborting and continuing after a good find.
        if (
            ConfigSingleton.is_initialized()
            and ConfigSingleton.config.optimization_toggles[
                "loosen-probing-agent-strictness"
            ]
        ):
            return """
            Be considerate in how much probing you will do. 
            Do not treat commands that you know or have been presented with as a `checklist` that you have to fully investigate. 
            The chance that a project has multiple build or test commands is very unlikely, so after you have identified (and verified) a command continue to investigate other aspects.
            Unless you see it especially specified in e.g. a README or toml, you can assume the project does not contain a linting command.
            """
        return ""  # Toggle is off, do nothing.

    @environment_probing_agent.instructions
    def add_brevity_instructions() -> str:
        # The probing agent sometimes asks for dumb commands over and over again, but we maybe want to limit our requests.
        if (
            ConfigSingleton.is_initialized()
            and ConfigSingleton.config.optimization_toggles[
                "probing-agent-instructions-for-saving-requests"
            ]
        ):
            return """
            You might be able to merge commands to do less requests and achieve more tasks at once. 
            An example when you are trying to call a tool for its version, but you are not sure whether its installed, you can do 
            `foo -version 2>/dev/null || echo "foo not installed"`

            You might also want to read multiple files at once or other similar combined actions. 
            Important: If you choose to do so, be considerate of the amount of output and that it stays traceable to a command. 
            Combining too many requests might introduce too much complexity or confusion at once. 
            """
        return ""  # Toggle is off, do nothing.

    @environment_probing_agent.instructions
    def add_partial_environment_instructions() -> str:
        return (
            """
        You are unlikely to achieve this all at once, so you are given a `PartialEnvironment` in your deps, 
        which is a mutable object for you to construct the information step by step. 
        Its fields are identical to your final outcome so once you finished it you can safely use it. 
        Consider populating the fields after each command. \n
        """
            + PartialEnvironment.get_output_instructions()
        )

    @environment_probing_agent.instructions
    def add_output_description(self) -> str:
        return (
            """
        -----------
        Output:

        We expect an `Environment` containing the key information relevant to act on the project.
        You have access to a `PartialEnvironment` object that you can fill step-by-step. 
        Once all fields are filled, return a complete Environment. Never fabricate data. Use existing state to skip work.
        """
            + "\n"
            + Environment.get_output_instructions()
        )

    return environment_probing_agent
