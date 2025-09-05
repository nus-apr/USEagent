"""
Main entry point for running one task.
"""

import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Literal, cast

from loguru import logger
from pydantic_core import to_jsonable_python

from useagent.agents.meta.agent import agent_loop
from useagent.pydantic_models.output.action import Action
from useagent.pydantic_models.output.answer import Answer
from useagent.pydantic_models.output.code_change import CodeChange
from useagent.pydantic_models.task_state import TaskState
from useagent.tasks.task import Task
from useagent.tools.meta import get_bash_history
from useagent.utils import log_commit_sha


def run(
    task: Task,
    output_dir: str,
    output_type: Literal[CodeChange, Answer, Action] = CodeChange,
):
    start_time_s = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    task_output_dir = Path(output_dir) / f"{task.uid}_{start_time_s}"
    task_output_dir.mkdir(parents=True, exist_ok=True)

    try:
        _run(task, task_output_dir, output_type=output_type)
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Error running task {task.uid}: {e} \n{tb}")
    finally:
        bash_history_file: Path = task_output_dir / "bash_commands.jsonl.log"
        logger.debug(f"Dumping Bash History to {bash_history_file}")
        with open(bash_history_file, "w") as f:
            for a, b, c in get_bash_history():
                json.dump({"command": a, "agent": b, "output": str(c)}, f)
                f.write("\n")


def _run(
    task: Task,
    task_output_dir: Path,
    output_type: Literal[CodeChange, Answer, Action] = CodeChange,
):
    logfile = Path(task_output_dir) / "info.log"
    logger.add(
        logfile,
        level="DEBUG",
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level>"
            " | <level>{message}</level>"
        ),
    )

    # construct task state
    task_state = TaskState(
        task=task,
        git_repo=task.git_repo,
    )

    # start main agent loop
    logger.info("Starting main agent loop")
    log_commit_sha()
    result, usage_tracker, messages = agent_loop(
        task_state, output_type=output_type, output_dir=task_output_dir
    )
    match result:
        case Action():
            cast_result: Action = cast(Action, result)
            logger.info(
                f"Task {task} completed with an {'succesful' if cast_result.success else 'unsuccesful'} Action:"
            )
            logger.info(f"\tEvidence: {cast_result.evidence}")
            logger.info(
                f"\tDoubts: {cast_result.doubts if cast_result.doubts else 'No Doubts'}"
            )
            if cast_result.execution_artifact:
                logger.info(f"\tExecution Artifact: {cast_result.execution_artifact}")
        case _:
            logger.info(f"Task {task} completed with result: {result}")

    usage_info_file: Path = task_output_dir / "usage.json.log"
    logger.debug(f"Storing Usage Information to {usage_info_file}")
    with open(usage_info_file, "w") as f:
        json.dump(usage_tracker.to_json(), f)

    if messages:
        message_file: Path = task_output_dir / "messages.jsonl.log"
        logger.debug(f"Storing {len(messages)} ModelMessages into {message_file}")
        with open(message_file, "w", encoding="utf-8") as f:
            for msg in messages:
                obj = to_jsonable_python(msg)
                f.write(json.dumps(obj) + "\n")
