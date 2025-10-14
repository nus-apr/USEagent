import contextlib
import os
import subprocess
from pathlib import Path

from loguru import logger


def run_command(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """
    Run a command in the shell.
    Args:
        - cmd: command to run
    """
    try:
        cp = subprocess.run(cmd, **kwargs)
    except subprocess.CalledProcessError as e:
        logger.warning(f"Error running command: {cmd}, {e}")
        raise e
    return cp


@contextlib.contextmanager
def cd(newdir):
    """
    Context manager for changing the current working directory
    :param newdir: path to the new directory
    :return: None
    """
    prevdir = os.getcwd()
    os.chdir(os.path.expanduser(newdir))
    try:
        yield
    finally:
        os.chdir(prevdir)


def log_commit_sha(path: str = "/commit.sha") -> None:
    commit_file = Path(path)
    if commit_file.exists():
        sha = commit_file.read_text().strip()
        logger.info(f"[Setup] Commit SHA: {sha}")
    else:
        logger.debug(f"[Setup] Commit file {commit_file} not found")
