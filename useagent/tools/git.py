import os
import subprocess
from pathlib import Path

from loguru import logger
from pydantic_ai import RunContext

from useagent.pydantic_models.artifacts.git import DiffEntry
from useagent.pydantic_models.common.constrained_types import NonEmptyStr
from useagent.pydantic_models.task_state import TaskState
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo

# DevNote:
# In theory, we can also use `git status` to identify `both_modified` entries from it.
# This does work for 'fresh' merges, but once agents start editing files, or worse commit half-baked things, these checks will fail.
# The safer way is to always check for the markers, regardless of the history.
# There is a tiny chance that these are part of the normal code, but that is really unlikely.


def check_for_merge_conflict_markers(
    path_to_file: Path, _silence_logger: bool = False
) -> bool:
    """
    Checks a given file for the existance of (any) merge conflict markers.
    Returns true if any merge conflict marker is found - even if they are not fully valid (e.g. they are remnants of a failed merge or incomplete edit).

    Args:
        path_to_file (Path): The path pointing to the file to check. File must exist.

    Returns:
        bool: True if the path contains any merge marker, false otherwise.
    """
    if not _silence_logger:
        logger.debug(
            f"[Tool] Called looking for Merge Conflict Markers in file {path_to_file}"
        )
    if not path_to_file or not isinstance(path_to_file, Path):
        raise ValueError("Received Empty, None or Non-Path Argument for path_to_file")
    abs_path_to_file: Path = path_to_file.absolute()
    if not abs_path_to_file.exists():
        raise ValueError(f"The path {abs_path_to_file} does not exist")
    if not abs_path_to_file.is_file():
        raise ValueError(
            f"Received a path_to_file {abs_path_to_file} that points to a folder, but a file is expected."
        )

    with open(abs_path_to_file, encoding="utf-8") as f:
        for line in f:
            if line.startswith(("<<<<<<<", "=======", ">>>>>>>")):
                logger.info(f"[Tool] Found Merge conflict marker in {abs_path_to_file}")
                return True
    # No Merge Conflicts Found
    return False


def find_merge_conflicts(path_to_check: Path) -> list[Path]:
    """
    Iterate over the given path to a folder, and look for any file that contains a merge marker.

    Args:
        path_to_check (Path): The path pointing to a folder to investigate. Will

    Returns:
        List[Path]: A list of all files that contain at least one merge marker. Can be empty if there are none.
    """
    logger.info(
        f"[Tool] Called looking for files with Merge Conflict Markers in path {path_to_check}"
    )
    if not path_to_check or not isinstance(path_to_check, Path):
        raise ValueError("Received Empty, None or Non-Path Argument for path_to_check")
    abs_path_to_check: Path = path_to_check.absolute()
    if not abs_path_to_check.exists():
        raise ValueError(f"The path {abs_path_to_check} does not exist")
    if abs_path_to_check.is_file():
        raise ValueError(
            f"Received a path_to_check {abs_path_to_check} that points to a file, but a folder is expected."
        )

    conflict_files: list[Path] = []
    for root, _, files in os.walk(abs_path_to_check):
        for name in files:
            path: Path = Path(os.path.join(root, name))
            if check_for_merge_conflict_markers(path, _silence_logger=True):
                conflict_files.append(path)
    logger.info(
        f"[Tool] Found {len(conflict_files)} files with merge conflicts within {path_to_check}"
    )
    return conflict_files


def view_commit_as_diff(
    ctx: RunContext[TaskState], commit_reference: NonEmptyStr
) -> DiffEntry | ToolErrorInfo:
    cwd: Path = Path(ctx.deps._git_repo.local_path)
    return _view_commit_as_diff(repository_path=cwd, commit_reference=commit_reference)


def _view_commit_as_diff(
    repository_path: Path, commit_reference: NonEmptyStr
) -> DiffEntry | ToolErrorInfo:
    logger.info(f"[Tool] viewing commit {commit_reference} of {str(repository_path)}")
    if not repository_path.is_dir():
        return ToolErrorInfo(
            message=f"Invalid repository path - this Tool seems to have been invoked out of place. You are trying to execute it at {repository_path}",
            supplied_arguments={
                "repository_path": str(repository_path),
                "commit_reference": str(commit_reference),
            },
        )

    if not (repository_path / ".git").is_dir():
        return ToolErrorInfo(
            message=f"The repository path {repository_path} is not a git repository",
            supplied_arguments={
                "repository_path": str(repository_path),
                "commit_reference": str(commit_reference),
            },
        )

    if not _commit_exists(repo=repository_path, commit=commit_reference):
        return ToolErrorInfo(
            message=f"Failed to identify commit {commit_reference} within the repository {repository_path.absolute()} - it likely does not exist",
            supplied_arguments={
                "repository_path": str(repository_path),
                "commit_reference": str(commit_reference),
            },
        )

    try:
        # A normal `git show`` would also have a header, so it would not be a DiffEntry.
        # This is why we have --format=--patch, which omits the header.
        # Also, -m is necessary to show content of merge commits
        cmd_out = subprocess.run(
            ["git", "show", "-m", "--pretty=format:", "--patch", commit_reference],
            cwd=repository_path,
            capture_output=True,
            text=True,
        )
        result = cmd_out.stdout
    except subprocess.CalledProcessError as e:
        return ToolErrorInfo(
            message=f"Failed to retrieve diff for commit {commit_reference}: {e.stderr.strip()}",
            supplied_arguments={
                "repository_path": str(repository_path),
                "commit_reference": str(commit_reference),
            },
        )

    if not result.strip():
        return ToolErrorInfo(
            message=f"Commit {commit_reference} exists but contains no diff",
            supplied_arguments={
                "repository_path": str(repository_path),
                "commit_reference": str(commit_reference),
            },
        )
    return DiffEntry(result)


def _commit_exists(repo: Path, commit: str) -> bool:
    try:
        return (
            subprocess.run(
                ["git", "cat-file", "-e", commit],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode
            == 0
        )
    except subprocess.CalledProcessError:
        return False


# DevNote:
# We could write tools for adding, removing, etc. basically everything related to git management and mirroring all git commands.
# But as of now this would be (a) lots of work and (b) basic bash tooling is quite ok with agents.
# So we give the VCS agent a Bash Tool and instructions how to use it in its prompt.
# There are some differences to this, e.g. viewing the patch, so that we can clearly get everything into our required data format.
