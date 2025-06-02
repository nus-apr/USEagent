"""
Main entry point for running one task.
"""

from datetime import datetime
from pathlib import Path

from loguru import logger

from app.tasks.usebench_task import UseBenchTask


def run(task: UseBenchTask, output_dir: str):
    start_time_s = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    task_output_dir = Path(output_dir) / f"{task.uid}_{start_time_s}"
    task_output_dir.mkdir(parents=True, exist_ok=True)

    try:
        _run(task, task_output_dir)
    except Exception as e:
        logger.error(f"Error running task {task.uid}: {e}")


def _run(task: UseBenchTask, task_output_dir: Path):

    logfile = Path(task_output_dir) / "info.log"
    logger.add(
        logfile,
        level="DEBUG",
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level>"
            " | <level>{message}</level>"
        ),
    )

    start_time = datetime.now()


