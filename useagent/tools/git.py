import os
import subprocess
from pathlib import Path

from loguru import logger
from pydantic_ai import RunContext

from useagent.pydantic_models.artifacts.git import DiffEntry
from useagent.pydantic_models.common.constrained_types import NonEmptyStr
from useagent.pydantic_models.task_state import TaskState
from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ArgumentEntry, ToolErrorInfo
from useagent.tools.run import run
from useagent.utils import cd


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
    # DevNote:
    # In theory, we can also use `git status` to identify `both_modified` entries from it.
    # This does work for 'fresh' merges, but once agents start editing files, or worse commit half-baked things, these checks will fail.
    # The safer way is to always check for the markers, regardless of the history.
    # There is a tiny chance that these are part of the normal code, but that is really unlikely.

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
    if not _is_utf_8_encoded(abs_path_to_file):
        # In case there is a non utf-8 file, we just assume there cannot be a merge marker.
        if not _silence_logger:
            logger.debug(
                f"[Tool] Skipping a non-utf-8 file at {abs_path_to_file} - assuming no merge markers"
            )
        return False
    with open(abs_path_to_file, encoding="utf-8") as f:
        for line in f:
            if line.startswith(("<<<<<<<", "=======", ">>>>>>>")):
                logger.info(f"[Tool] Found Merge conflict marker in {abs_path_to_file}")
                return True
    # No Merge Conflicts Found
    return False


def _is_utf_8_encoded(path: Path) -> bool:
    # DevNote:
    # We can see issues if the file tries to be opened with utf-8 but it's e.g. an image or just spanish.
    # This is more common than you would think, because some projects have translation files.
    try:
        with open(path, "rb") as f:
            for line in f:
                line.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def find_merge_conflicts(path_to_check: Path) -> list[Path]:
    """
    Iterate over the given path to a folder, and look for any file that contains a merge marker.

    Args:
        path_to_check (Path): The path pointing to a folder to investigate.

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
    """
    Retrieve a given commit in the repository and view it as a diff-entry.
    Any valid commit in the current history can be seen this way.

    Args:
        commit_reference (str): A non-empty string representing either a git commit hash, or other valid commit references like HEAD. Abbreviated hashes are supported, as long as they are unique.

    Returns:
        DiffEntry | ToolErrorInfo: Returns a DiffEntry of the specified commit on a succesful retrieval, or a ToolErrorInfo containing a message of the issue if any problem occured.
    """
    cwd: Path = Path(ctx.deps._git_repo.local_path)
    return _view_commit_as_diff(repository_path=cwd, commit_reference=commit_reference)


def _view_commit_as_diff(
    repository_path: Path, commit_reference: NonEmptyStr
) -> DiffEntry | ToolErrorInfo:
    logger.info(f"[Tool] viewing commit {commit_reference} of {str(repository_path)}")
    if not repository_path.is_dir():
        return ToolErrorInfo(
            message=f"Invalid repository path - this Tool seems to have been invoked out of place. You are trying to execute it at {repository_path}",
            supplied_arguments=[
                ArgumentEntry("repository_path", str(repository_path)),
                ArgumentEntry("commit_reference", str(commit_reference)),
            ],
        )

    if not (repository_path / ".git").is_dir():
        return ToolErrorInfo(
            message=f"The repository path {repository_path} is not a git repository",
            supplied_arguments=[
                ArgumentEntry("repository_path", str(repository_path)),
                ArgumentEntry("commit_reference", str(commit_reference)),
            ],
        )

    if not _commit_exists(repo=repository_path, commit=commit_reference):
        return ToolErrorInfo(
            message=f"Failed to identify commit {commit_reference} within the repository {repository_path.absolute()} - it likely does not exist",
            supplied_arguments=[
                ArgumentEntry("repository_path", str(repository_path)),
                ArgumentEntry("commit_reference", str(commit_reference)),
            ],
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
            supplied_arguments=[
                ArgumentEntry("repository_path", str(repository_path)),
                ArgumentEntry("commit_reference", str(commit_reference)),
            ],
        )

    if not result.strip():
        return ToolErrorInfo(
            message=f"Commit {commit_reference} exists but contains no diff",
            supplied_arguments=[
                ArgumentEntry("repository_path", str(repository_path)),
                ArgumentEntry("commit_reference", str(commit_reference)),
            ],
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


async def extract_diff(
    project_dir: Path | str | None = None,
) -> CLIResult | ToolErrorInfo:
    """
    Extract the diff of the current state of the repository.
    This is achieved using `git diff` for both cached and uncached, i.E. will show all files in the index.
    This will also add all files in the current repository to the index using `git add .`
    For extracting other, existing diffs from commits consider `view_commit_as_diff`.
    This tool does NOT make a commit.

    Args:
        project_dir(Path|str|None, default None): Path at which to execute the extraction. If None, the current project dir will be used.

    Returns:
        CLIResult: The result of the diff extraction, or a ToolErrorInfo containing information of a miss-usage or command failure.
                   The CLIResult will contain all information necessary to form a diff, but it is not a diff itself.
    """
    project_dir = project_dir or Path(".").absolute()

    logger.info(
        f"[Tool] Invoked edit_tool `extract_diff`. Extracting a patch from {project_dir} (type: {type(project_dir)})"
    )

    with cd(project_dir):
        await run(
            "git add ."
        )  # Git Add is necessary to see changes to newly created files
        _, cached_out, stderr_1 = await run("git diff --cached")
        _, working_out, stderr_2 = await run("git diff")
        stdout = cached_out + working_out

        if stderr_1 or stderr_2:
            return ToolErrorInfo(
                message=f"Failed to extract diff: {stderr_1 + stderr_2}",
                supplied_arguments=[ArgumentEntry("project_dir", str(project_dir))],
            )

        if not stdout or not stdout.strip():
            logger.debug("[Tool] edit_tool `extract_diff`: Received empty Diff")
            return CLIResult(output="No changes detected in the repository.")
        logger.debug(
            f"[Tool] edit_tool `extract_diff`: Received {stdout[:25]} ... from {project_dir}"
        )
        return CLIResult(output=f"Here's the diff of the current state:\n{stdout}")


# DevNote:
# We could write tools for adding, removing, etc. basically everything related to git management and mirroring all git commands.
# But as of now this would be (a) lots of work and (b) basic bash tooling is quite ok with agents.
# So we give the VCS agent a Bash Tool and instructions how to use it in its prompt.
# There are some differences to this, e.g. viewing the patch, so that we can clearly get everything into our required data format.
