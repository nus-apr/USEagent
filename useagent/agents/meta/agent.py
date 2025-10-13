from pathlib import Path
from typing import Literal

from loguru import logger
from pydantic_ai import Agent, RunContext
from pydantic_ai.tools import Tool
from pydantic_ai.usage import UsageLimits

import useagent.common.constants as constants
from useagent.common.context_window import fit_messages_into_context_window
from useagent.config import AppConfig, ConfigSingleton
from useagent.microagents.decorators import (
    alias_for_microagents,
    conditional_microagents_triggers,
)
from useagent.microagents.management import load_microagents_from_project_dir
from useagent.pydantic_models.artifacts.git.diff import DiffEntry
from useagent.pydantic_models.common.constrained_types import NonEmptyStr
from useagent.pydantic_models.output.action import Action
from useagent.pydantic_models.output.answer import Answer
from useagent.pydantic_models.output.code_change import CodeChange
from useagent.pydantic_models.provides_output_instructions import (
    ProvidesOutputInstructions,
)
from useagent.pydantic_models.task_state import TaskState
from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo
from useagent.state.usage_tracker import UsageTracker
from useagent.tasks.swebench_task import SWEbenchTask
from useagent.tools.bash import (
    get_bash_history,
    init_bash_tool,
    make_bash_tool_for_agent,
)
from useagent.tools.edit import init_edit_tools
from useagent.tools.meta import (  # Agent-State Tools; Agent-Agent Tools
    _gather_checklist,
    _set_usage_tracker,
    advising_on_doubts,
    edit_code,
    execute_tests,
    probe_environment,
    search_code,
    vcs,
    view_command_history,
)

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.md").read_text()


@conditional_microagents_triggers(load_microagents_from_project_dir())
@alias_for_microagents("META")
def init_agent(
    config: AppConfig | None = None,
    output_type: Literal[CodeChange, Answer, Action] = CodeChange,
) -> Agent[TaskState, CodeChange | Answer]:
    if config is None:
        config = ConfigSingleton.config
    assert config is not None

    meta_agent = Agent(
        config.model,
        instructions=SYSTEM_PROMPT,
        deps_type=TaskState,
        retries=constants.META_AGENT_RETRIES,
        output_retries=constants.META_AGENT_OUTPUT_RETRIES,
        tools=[
            # Non-Agentic Tools
            # TODO: Do we want to deprecate this? Things are a bit weird after #44
            # Tool(select_diff_from_diff_store, takes_ctx=True, max_retries=3),
            # Tool(view_task_state, takes_ctx=True, max_retries=0),
            Tool(view_command_history, max_retries=2),
            Tool(
                make_bash_tool_for_agent(
                    "META",
                    bash_call_delay_in_seconds=constants.META_AGENT_BASH_TOOL_DELAY,
                ),
                max_retries=4,
            ),
            # TODO: Figure out how to make this work with SWE - we often see a patch as a full file rather than a delta.
            # Tool(read_file_as_diff),
            # Agent-Agent Tools
            Tool(edit_code, takes_ctx=True, max_retries=constants.EDIT_CODE_RETRIES),
            Tool(
                search_code, takes_ctx=True, max_retries=constants.SEARCH_AGENT_RETRIES
            ),
            Tool(
                probe_environment,
                takes_ctx=True,
                max_retries=constants.PROBE_ENVIRONMENT_RETRIES,
            ),
            Tool(
                execute_tests,
                takes_ctx=True,
                max_retries=constants.EXECUTE_TESTS_RETRIES,
            ),
            Tool(vcs, takes_ctx=True, max_retries=constants.VCS_AGENT_RETRIES),
        ],
        output_type=output_type,
        history_processors=[fit_messages_into_context_window],
    )

    ## This adds the task description to instructions (SYSTEM prompt).
    @meta_agent.instructions
    def add_task_description(ctx: RunContext[TaskState]) -> str:
        """Add a task description to the TaskState.

        Args:
            task_description (str): The description of the task to be added.
        """
        return ctx.deps._task.get_issue_statement()

    ## Depending on the output type (if possible), describes the expected output format.
    @meta_agent.instructions
    def add_output_description() -> str:
        if isinstance(output_type, ProvidesOutputInstructions):
            logger.trace(
                f"[Setup] MetaAgent is expected to output a `{str(output_type)}`, adding output instructions."
            )
            return (
                f"""
            ---------------------------------------------------
            Output:

            You are expected to return a `{str(output_type)}`.
            """
                + output_type.get_output_instructions()
            )
        else:
            logger.warning(
                "[Setup] MetaAgent received a output type that did not implement the `get_output_instructions` method and will have less info."
            )
            return f"Output: You are expected to return a `{output_type}`"

    ### Define actions as tools to meta_agent. Each action interfaces to another agent in Pydantic AI.

    ### Action definitions END

    return meta_agent


def agent_loop(
    task_state: TaskState,
    output_type: Literal[CodeChange, Answer, Action] = CodeChange,
    output_dir: Path | None = None,
):
    """
    Main agent loop.
    """
    # first initialize some of the tools based on the task.
    init_bash_tool(
        str(task_state._task.get_working_directory()),
        command_transformer=task_state._task.command_transformer,
    )
    init_edit_tools(str(task_state._task.get_working_directory()))

    USAGE_TRACKER = UsageTracker()
    _set_usage_tracker(USAGE_TRACKER)
    meta_agent = init_agent(output_type=output_type)
    # actually running the agent
    prompt = "Invoke tools to complete the task."
    result = meta_agent.run_sync(
        prompt,
        deps=task_state,
        usage_limits=UsageLimits(request_limit=constants.META_AGENT_REQUEST_LIMIT),
    )
    USAGE_TRACKER.add(meta_agent.name, result.usage())
    last_iteration_messages = result.all_messages()

    if (
        ConfigSingleton.is_initialized()
        and ConfigSingleton.config.optimization_toggles["reiterate-on-doubts"]
    ):
        DOUBT_REITERATION = 0
        while (
            DOUBT_REITERATION < constants.MAX_DOUBT_REITERATIONS
            and result.output
            and result.output.doubts
            and result.output.doubts.lower() != "none"
            and result.output.doubts.lower() != "none."
            and result.output.doubts.lower() != "no"
            and result.output.doubts.lower() != "no."
        ):
            try:
                # TODO: store the result? To have something in case of timeout?
                logger.info(
                    f"[MetaAgent] Attempt at solving the task produced a result with doubts: {result.output.doubts}. Attempting to resolve doubts with changes (RE-ITERATION {DOUBT_REITERATION})"
                )
                logger.debug(f"[MetaAgent] Doubtful result was: {result.output}")
                current_bash_hist: list[
                    tuple[
                        NonEmptyStr, NonEmptyStr, CLIResult | ToolErrorInfo | Exception
                    ]
                ] = get_bash_history()[:10]
                bash_infos = [
                    "command\t" + t[0] + "outcome:\t" + str(t[2])
                    for t in current_bash_hist
                ]

                artifact = "UNK"
                match result.output:
                    case Action():
                        artifact = (
                            "SUCCESSFUL"
                            if result.output.success
                            else "UNSUCCESSFUL" + "---" + result.output.evidence
                        )
                    case Answer():
                        artifact = result.output.answer
                    case CodeChange():
                        artifact = (
                            f"Chosen ID: {result.output.diff_id} , which references this patch:"
                            + str(
                                task_state.diff_store.id_to_diff[result.output.diff_id]  # type: ignore
                            )
                            + "\nExplanation:"
                            + result.output.explanation
                        )
                    case _:
                        artifact = str(result.output)
                new_instruction: str = advising_on_doubts(
                    artifact=artifact,
                    doubts=result.output.doubts,
                    task_desc=task_state._task.get_issue_statement(),
                    cmd_history=bash_infos,
                )

                checklist = _gather_checklist(
                    task_instruction=new_instruction,
                    task_state=task_state,
                    cmd_history=bash_infos,
                    environment=task_state.active_environment,
                )
                new_instruction += f"\n Checklist:\n {str(checklist)}"

                result = meta_agent.run_sync(
                    new_instruction,
                    deps=task_state,
                    usage_limits=UsageLimits(
                        request_limit=constants.META_AGENT_REQUEST_LIMIT
                    ),
                    message_history=last_iteration_messages,
                )
                # TODO: Do we want to earmark this as 'META-reiteration'? At the moment it will just be 2nd Meta Agent Cost
                USAGE_TRACKER.add(meta_agent.name, result.usage())
                last_iteration_messages = result.all_messages()
            except Exception as exc:
                logger.error(
                    f"[MetaAgent] Error while re-iterating the result after doubts. Re-using previous, initial result (with doubts). Exception was: {exc}"
                )
            finally:
                DOUBT_REITERATION += 1
        else:
            logger.debug("[MetaAgent] Task was finished without any doubts.")

    if isinstance(result.output, CodeChange):
        diff_id = result.output.diff_id
        logger.info(f"[Post-Processing] Resolving {diff_id} in DiffStore:")
        try:
            diff_entry: DiffEntry | None = task_state.diff_store.id_to_diff[diff_id]  # type: ignore
            diff_content: str = (
                diff_entry.diff_content
                if diff_entry
                else f"FAILED to retrieve diff_content for diff_id {diff_id}"
            )
            if diff_content and output_dir:
                patch_file = output_dir / "patch.diff"
                patch_file.parent.mkdir(parents=True, exist_ok=True)
                patch_file.write_text(diff_content)
                logger.debug(f"[Post-Processing] Wrote chosen patch to {patch_file}")
            if output_dir and isinstance(task_state._task, SWEbenchTask):
                task_state._task.postprocess_swebench_task(diff_content, output_dir)
        except Exception as e:
            logger.error(
                f"[Post-Processing] Issue finding {diff_id} in DiffStore {task_state.diff_store}"
            )
            logger.error(e)

    return result.output, USAGE_TRACKER, result.all_messages()
