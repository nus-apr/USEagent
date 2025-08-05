"""
Main entry point for running one task.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from loguru import logger

from useagent.agents.meta.agent import agent_loop
from useagent.pydantic_models.output.action import Action
from useagent.pydantic_models.output.answer import Answer
from useagent.pydantic_models.output.code_change import CodeChange
from useagent.pydantic_models.task_state import TaskState
from useagent.tasks.task import Task
from useagent.tools.meta import get_bash_history


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
        logger.error(f"Error running task {task.uid}: {e}")
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
    result, usage_tracker = agent_loop(task_state)
    logger.info(f"Task {task} completed with result: {result}")

    usage_info_file: Path = task_output_dir / "usage.json.log"
    logger.debug(f"Storing Usage Information to {usage_info_file}")
    with open(usage_info_file, "w") as f:
        json.dump(usage_tracker.to_json(), f)
