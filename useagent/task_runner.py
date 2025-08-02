"""
Main entry point for running one task.
"""

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
    result = agent_loop(task_state, output_type=output_type)
    logger.info(f"Task {task} completed with result: {result}")
