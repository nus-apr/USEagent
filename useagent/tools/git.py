import os
import shlex
import subprocess
from collections.abc import Sequence
from pathlib import Path

from loguru import logger
from pydantic_ai import RunContext

from useagent.common.encoding import is_utf_8_encoded
from useagent.config import ConfigSingleton
from useagent.pydantic_models.artifacts.git.diff import DiffEntry
from useagent.pydantic_models.artifacts.git.diff_store import DiffEntryKey
from useagent.pydantic_models.common.constrained_types import NonEmptyStr
from useagent.pydantic_models.task_state import TaskState
from useagent.pydantic_models.tools.errorinfo import ArgumentEntry, ToolErrorInfo
from useagent.tools.run import run

_EXTRACT_GIT_COUNTER: int = 0


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
    if not is_utf_8_encoded(abs_path_to_file):
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
    ctx: RunContext[TaskState],
    paths_to_extract: str | Path | Sequence[str | Path] | None = None,
) -> DiffEntryKey | ToolErrorInfo:
    """
    Extract a git-diff of the current state of the repository.
    This is achieved using `git diff` for both cached and uncached, i.E. will show all files in the index.
    Hidden files and folders are always excluded - you are not supposed to make changes to them.
    This will also add files in the requested scope to the index using `git add`.
    This tool does NOT make a commit.

    Extraction scope:
        Limit extraction via `paths_to_extract` (dir, file, glob/pathspec, or list). If empty/None, use ".".
        Values are passed to git as-is; absolute paths are allowed (git must resolve them inside the repo).

    Post-condition:
        After extracting the diff, all staged changes are **unstaged** (via `git reset`) before returning.
        Working tree changes are not reverted.

    Args:
        paths_to_extract(str|Path|Sequence|None): Single path/pattern or list. None/empty -> ["."]. Single value is wrapped.

    Returns:
        DiffEntryKey or ToolErrorInfo
    """
    # DevNote:  The _exclude_hidden_dir is now always on - you can never use this tool here to get a .venv at the moment.
    _exclude_hidden_folders_and_files_from_diff: bool = True

    extract_result: DiffEntry | ToolErrorInfo = await _extract_diff(
        exclude_hidden_folders_and_files_from_diff=_exclude_hidden_folders_and_files_from_diff,
        paths_to_extract=paths_to_extract,
    )
    if isinstance(extract_result, ToolErrorInfo):
        return extract_result

    global _EXTRACT_GIT_COUNTER
    try:
        diff_id: DiffEntryKey = ctx.deps.diff_store._add_entry(extract_result)
        _EXTRACT_GIT_COUNTER = 0
        return diff_id
    except ValueError as verr:
        if "diff already exists" in str(verr):
            _EXTRACT_GIT_COUNTER += 1
            existing_diff_id: DiffEntryKey = ctx.deps.diff_store.diff_to_id[  # type: ignore
                extract_result.diff_content
            ]
            if (
                ConfigSingleton.is_initialized()
                and ConfigSingleton.config.optimization_toggles[
                    "block-repeated-git-extracts"
                ]
                and _EXTRACT_GIT_COUNTER >= 2
            ):
                return _make_repeated_extract_diff_tool_error(
                    existing_diff_id, extract_result.diff_content
                )
            return ToolErrorInfo(
                message=f"`extract_diff` returned a diff identical to {existing_diff_id}. "
                f"Reuse that id or make further changes.\n"
                f"Preview:\n{_preview_patch(extract_result.diff_content)}",
                supplied_arguments=[
                    ArgumentEntry("paths_to_extract", str(paths_to_extract))
                ],
            )
        raise
    except Exception as ex:
        return ToolErrorInfo(
            message=f"Unhandled exception during diff-extraction ({ex})",
            supplied_arguments=[
                ArgumentEntry("paths_to_extract", str(paths_to_extract))
            ],
        )


async def _extract_diff(
    exclude_hidden_folders_and_files_from_diff: bool = True,
    paths_to_extract: str | Path | Sequence[str | Path] | None = None,
) -> DiffEntry | ToolErrorInfo:
    # normalize to a flat list of strings; default to ["."]
    if paths_to_extract is None:
        includes: list[str] = ["."]
    elif isinstance(paths_to_extract, (str, Path)):
        includes = [str(paths_to_extract)]
    else:
        includes = [str(p) for p in paths_to_extract]

    include_spec = shlex.join(includes)

    exclude_specs: list[str] = []
    if exclude_hidden_folders_and_files_from_diff:
        exclude_specs.extend(
            [
                "':(glob,exclude)**/.*'",
                "':(glob,exclude)**/.*/**'",
                "':(glob,exclude).venv/**'",
                "':(glob,exclude)venv/**'",
            ]
        )
    exclude_spec = " " + " ".join(exclude_specs) if exclude_specs else ""

    try:
        # Stage new files in scope (but not commit)
        git_add_cmd = f"git add --intent-to-add {include_spec}{exclude_spec}"
        await run(git_add_cmd, truncate_after=None)

        # Extract diff for scope
        diff_cmd = (
            "git -c core.pager=cat --no-pager "
            "diff --no-color --no-ext-diff --text --patch HEAD -- "
            f"{include_spec}{exclude_spec}"
        )
        exit_code, stdout, stderr = await run(diff_cmd, truncate_after=None)

        if exit_code != 0 and stderr:
            return ToolErrorInfo(
                message=f"Failed to extract diff: {stderr}",
                supplied_arguments=[
                    ArgumentEntry("paths_to_extract", str(paths_to_extract))
                ],
            )
        if not stdout or not stdout.strip():
            return ToolErrorInfo(
                message="No changes detected. (Maybe only gitignored/hidden files changed?)",
                supplied_arguments=[
                    ArgumentEntry("paths_to_extract", str(paths_to_extract))
                ],
            )

        output = stdout if stdout.endswith("\n") else stdout + "\n"
        if len(output.splitlines()) > 2500:
            return ToolErrorInfo(
                message=f"Patch too large: {len(output.splitlines())} lines.",
                supplied_arguments=[
                    ArgumentEntry("paths_to_extract", str(paths_to_extract))
                ],
            )

        return DiffEntry(output)
    finally:
        # Unstage everything; do not touch working tree
        try:
            await run("git reset --quiet", truncate_after=None)
        except Exception as ex:
            logger.warning(f"[Tool] Failed to unstage changes: {ex}")


def _make_repeated_extract_diff_tool_error(
    diff_id: str, diff_content: str
) -> ToolErrorInfo:
    message: str = f"""
    You are asking repeatedly for `extract_diff` while seeing the same results. 
    You are likely stuck. The `extract_diff` will not give you any new results unless you make further changes to the files. 
    You maybe have only made changes to hidden files or derivate files outside of the actual project source code. 
    Check whether you have (successfully) called any tool that makes any file changes - if not, you must make changes using other tools before calling this method.

    Consider: Have you made all the changes requested from you? 
    If yes, return an existing diff_id. 
    If no, make further changes, and only then call `extract_diff` again. 

    Remember: The changes will be validated upstream - you don't have to completely verify their correctness. 
    
    You keep on receiving this diff_id: {diff_id}

    Which represents this patch:\n
    {diff_content}
    """
    return ToolErrorInfo(message=message)


def _preview_patch(patch: str) -> str:
    NUMBER_OF_PREVIEW_LINES: int = 10
    if not patch or not patch.strip():
        return "<< received empty patch >>"
    if len(patch.splitlines()) <= NUMBER_OF_PREVIEW_LINES:
        return patch

    POSTFIX: str = " [[ End of Preview - Patch is longer ]]"
    return "\n".join(patch.splitlines()[:10] + [POSTFIX])


# DevNote:
# We could write tools for adding, removing, etc. basically everything related to git management and mirroring all git commands.
# But as of now this would be (a) lots of work and (b) basic bash tooling is quite ok with agents.
# So we give the VCS agent a Bash Tool and instructions how to use it in its prompt.
# There are some differences to this, e.g. viewing the patch, so that we can clearly get everything into our required data format.
