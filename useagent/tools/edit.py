import os
from pathlib import Path

from loguru import logger

from useagent.common.context_window import fit_message_into_context_window
from useagent.common.guardrails import useagent_guard_rail
from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ArgumentEntry, ToolErrorInfo
from useagent.tools.run import maybe_truncate, run
from useagent.utils import cd

SNIPPET_LINES: int = 4

_project_dir: Path | None = None


def init_edit_tools(project_dir: str):
    if not project_dir or (isinstance(project_dir, str) and not (project_dir.strip())):
        raise ValueError(
            "Cannot initialize edit-tool without a valid project dir - was given `None` or empty string."
        )
    global _project_dir
    _project_dir = Path(project_dir)


def _make_path_absolute(path: str) -> Path:
    assert _project_dir is not None, "Project directory must be initialized first."
    if os.path.isabs(path):
        return Path(path)
    return _project_dir / path


def _read_file(path: Path) -> str | ToolErrorInfo:
    try:
        return path.read_text()
    except Exception as e:
        return ToolErrorInfo(
            message=f"Ran into {e} while trying to read {path}",
            supplied_arguments=[ArgumentEntry("path", str(path))],
        )


def _write_file(path: Path, file: str):
    try:
        path.write_text(file)
    except Exception as e:
        return ToolErrorInfo(
            message=f"Ran into {e} while trying to write to {path}",
            supplied_arguments=[ArgumentEntry("path", str(path))],
        )


def _make_output(
    file_content: str,
    file_descriptor: str,
    init_line: int = 1,
    expand_tabs: bool = True,
):
    file_content = maybe_truncate(file_content)
    if expand_tabs:
        file_content = file_content.expandtabs()
    file_content = "\n".join(
        [
            f"{i + init_line:6}\t{line}"
            for i, line in enumerate(file_content.split("\n"))
        ]
    )
    return (
        f"Here's the result of running `cat -n` on {file_descriptor}:\n"
        + file_content
        + "\n"
    )


async def view(
    file_path: str, view_range: list[int] | None = None
) -> CLIResult | ToolErrorInfo:
    """
    View the content of a file or directory at the specified path.
    If view_range is provided, only the specified lines will be returned.

    Args:
        file_path (str): The relative path to the file or directory.
        view_range (list[int] | None): A list of two integers specifying the range of lines to view. Only applicable to files, not directories.

    Returns:
        CLIResult: The result of the view operation, containing the output and a short header summarizing the used command.
    """
    logger.info(
        f"[Tool] Invoked edit_tool `view`. Viewing {file_path}, range {view_range}"
    )
    try:
        supplied_arguments = [
            ArgumentEntry("file_path", str(file_path)),
            ArgumentEntry("view_range", str(view_range)),
        ]
    except ValueError:
        supplied_arguments = []

    if not file_path or not file_path.strip():
        return ToolErrorInfo(
            message="Received an empty or None file_path",
            supplied_arguments=supplied_arguments,
        )

    path = _make_path_absolute(file_path)

    if (
        guard_rail_tool_error := useagent_guard_rail(
            file_path, supplied_arguments=supplied_arguments
        )
    ) is not None:
        return guard_rail_tool_error

    if not path.exists():
        return ToolErrorInfo(
            message=f"Filepath {file_path} does not exist.",
            supplied_arguments=supplied_arguments,
        )
    if path.is_dir():
        if view_range:
            return ToolErrorInfo(
                message="The `view_range` parameter is not allowed when `path` points to a directory.",
                supplied_arguments=supplied_arguments,
            )

        _, stdout, stderr = await run(rf"find {path} -maxdepth 2 -not -path '*/\.*'")
        if not stderr:
            stdout = f"Here's the files and directories up to 2 levels deep in {path}, excluding hidden items:\n{stdout}\n"
            return CLIResult(output=stdout)
        if not stdout:
            return CLIResult(error=stderr, output=None)
        return CLIResult(output=stdout, error=stderr)

    _read_file_result = _read_file(path)
    if isinstance(_read_file_result, ToolErrorInfo):
        return _read_file_result
    file_content = _read_file_result
    init_line = 1
    if view_range:
        if len(view_range) != 2 or not all(isinstance(i, int) for i in view_range):
            return ToolErrorInfo(
                message="Invalid `view_range`. It should be a list of two integers.",
                supplied_arguments=supplied_arguments,
            )
        file_lines = file_content.split("\n")
        n_lines_file = len(file_lines)
        init_line, final_line = view_range
        if init_line < 1 or init_line > n_lines_file:
            return ToolErrorInfo(
                message=f"Invalid `view_range`: {view_range}. Its first element `{init_line}` should be within the range of lines of the file: {[1, n_lines_file]}",
                supplied_arguments=supplied_arguments,
            )
        if final_line > n_lines_file:
            return ToolErrorInfo(
                message=f"Invalid `view_range`: {view_range}. Its second element `{final_line}` should be smaller than the number of lines in the file: `{n_lines_file}`",
                supplied_arguments=supplied_arguments,
            )
        if final_line != -1 and final_line < init_line:
            return ToolErrorInfo(
                message=f"Invalid `view_range`: {view_range}. Its second element `{final_line}` should be larger or equal than its first `{init_line}`",
                supplied_arguments=supplied_arguments,
            )

        if final_line == -1:
            file_content = "\n".join(file_lines[init_line - 1 :])
        else:
            file_content = "\n".join(file_lines[init_line - 1 : final_line])

    # Possibly: Files are large, and exceed the context window. We account for them by optionally shortening them, if configured.
    file_content = fit_message_into_context_window(file_content)

    return CLIResult(output=_make_output(file_content, str(path), init_line=init_line))


async def create(file_path: str, file_text: str) -> CLIResult | ToolErrorInfo:
    """
    Create a new file at the specified path with the given text content.
    Text content can be empty.
    Path must be a valid path that does not exist, path cannot be empty or 'None'.

    Args:
        file_path (str): The path where the new file will be created.
        file_text (str): The text content to write into the new file.

    Returns:
        CLIResult: The result of the create operation, indicating success or failure.
    """
    logger.info(
        f"[Tool] Invoked edit_tool `create`. Creating {file_path}, content preview: {file_text[:15]} ..."
    )

    try:
        supplied_arguments = [
            ArgumentEntry("file_path", str(file_path)),
            ArgumentEntry("file_text", str(file_text)),
        ]
    except ValueError:
        supplied_arguments = []
    if not file_path or not file_path.strip():
        return ToolErrorInfo(
            message="Received an None or Empty file_path argument.",
            supplied_arguments=[
                ArgumentEntry("file_path", str(file_path)),
                ArgumentEntry("file_text", str(file_text)),
            ],
        )

    path = _make_path_absolute(file_path)

    if (
        guard_rail_tool_error := useagent_guard_rail(
            file_path, supplied_arguments=supplied_arguments
        )
    ) is not None:
        return guard_rail_tool_error

    if path.exists():
        return ToolErrorInfo(
            message=f"File already exists at: {path}. Cannot overwrite files using command `create`.",
            supplied_arguments=supplied_arguments,
        )

    _write_file(path, file_text)
    return CLIResult(output=f"File created successfully at: {file_path}")


async def str_replace(file_path: str, old_str: str, new_str: str):
    """
    Replace old_str with new_str in the content of the file at the specified path.

    Args:
        file_path (str): The path to the file where the replacement will occur.
        old_str (str): The string to be replaced.
        new_str (str): The string to replace with.

    Returns:
        CLIResult: The result of the str_replace operation, containing the output or error.
    """
    logger.info(
        f"[Tool] Invoked edit_tool `str_replace`. Replacing {old_str} for {new_str} in {file_path}"
    )

    path = _make_path_absolute(file_path)

    try:
        supplied_arguments = [
            ArgumentEntry("file_path", str(file_path)),
            ArgumentEntry("old_str", str(old_str if old_str else "empty string")),
            ArgumentEntry("new_str", str(new_str if new_str else "empty string")),
        ]
    except ValueError:
        supplied_arguments = []

    if (
        guard_rail_tool_error := useagent_guard_rail(
            file_path, supplied_arguments=supplied_arguments
        )
    ) is not None:
        return guard_rail_tool_error
    if not path.exists():
        return ToolErrorInfo(
            message=f"Filepath {file_path} does not exist, it has to be created first. `str_replace` only works for existing files.",
            supplied_arguments=supplied_arguments,
        )
    if path.is_dir():
        return ToolErrorInfo(
            message=f"Filepath {file_path} is a directory - `str_replace` can only be applied to files.",
            supplied_arguments=supplied_arguments,
        )

    _read_file_result = _read_file(path)
    if isinstance(_read_file_result, ToolErrorInfo):
        return _read_file_result
    file_content = _read_file_result.expandtabs()
    if not old_str or not old_str.strip():
        return ToolErrorInfo(
            message=f"You are trying to replace an empty- or whitespace-string in {file_path}. This is not expected behaviour, consider using an insert or a different action.",
            supplied_arguments=supplied_arguments,
        )
    old_str = old_str.expandtabs()

    new_str = new_str.expandtabs()

    occurrences = file_content.count(old_str)
    if occurrences == 0:
        return ToolErrorInfo(
            message=f"No replacement was performed, old_str `{old_str}` did not appear verbatim in {path}.",
            supplied_arguments=supplied_arguments,
        )
    elif occurrences > 1:
        file_content_lines = file_content.split("\n")
        lines = [
            idx + 1 for idx, line in enumerate(file_content_lines) if old_str in line
        ]
        return ToolErrorInfo(
            message=f"No replacement was performed. Multiple occurrences of old_str `{old_str}` in lines {lines}. Please ensure it is unique",
            supplied_arguments=supplied_arguments,
        )

    new_file_content = file_content.replace(old_str, new_str)

    _write_file(path, new_file_content)

    replacement_line = file_content.split(old_str)[0].count("\n")
    start_line = max(0, replacement_line - SNIPPET_LINES)
    end_line = replacement_line + SNIPPET_LINES + new_str.count("\n")
    snippet = "\n".join(new_file_content.split("\n")[start_line : end_line + 1])

    success_msg = f"The file {path} has been edited. "
    success_msg += _make_output(snippet, f"a snippet of {path}", start_line + 1)
    success_msg += "Review the changes and make sure they are as expected. Edit the file again if necessary."

    return CLIResult(output=success_msg)


async def insert(
    file_path: str, insert_line: int, new_str: str
) -> CLIResult | ToolErrorInfo:
    """
    Insert new_str at the specified line in the file at the given path.

    Args:
        file_path (str): The path to the file where the insertion will occur.
        insert_line (int): The line number at which to insert new_str (0-indexed).
        new_str (str): The string to insert into the file.

    Returns:
        CLIResult: The result of the insert operation, containing the output or error.
    """
    logger.info(
        f"[Tool] Invoked edit_tool `insert`. Inserting {new_str} at L{insert_line} in {file_path}"
    )

    path = _make_path_absolute(file_path)

    try:
        supplied_arguments = [
            ArgumentEntry("file_path", str(file_path)),
            ArgumentEntry("insert_line", str(insert_line)),
            ArgumentEntry("new_str", str(new_str)),
        ]
    except ValueError:
        supplied_arguments = []

    if (
        guard_rail_tool_error := useagent_guard_rail(
            file_path, supplied_arguments=supplied_arguments
        )
    ) is not None:
        return guard_rail_tool_error

    if not path.exists():
        return ToolErrorInfo(
            message=f"Filepath {file_path} does not exist, it has to be created first. `insert` only works for existing files.",
            supplied_arguments=supplied_arguments,
        )
    if path.is_dir():
        return ToolErrorInfo(
            message=f"Filepath {file_path} is a directory - `insert` can only be applied to files.",
            supplied_arguments=supplied_arguments,
        )

    _read_file_result = _read_file(path)
    if isinstance(_read_file_result, ToolErrorInfo):
        return _read_file_result
    file_text = _read_file_result.expandtabs()
    new_str = new_str.expandtabs()
    file_text_lines = file_text.split("\n")
    n_lines_file = len(file_text_lines)

    if insert_line < 0 or insert_line > n_lines_file:
        return ToolErrorInfo(
            message=f"Invalid `insert_line` parameter: {insert_line}. It should be within the range of lines of the file: {[0, n_lines_file]}",
            supplied_arguments=supplied_arguments,
        )

    new_str_lines = new_str.split("\n")
    new_file_text_lines = (
        file_text_lines[:insert_line] + new_str_lines + file_text_lines[insert_line:]
    )
    snippet_lines = (
        file_text_lines[max(0, insert_line - SNIPPET_LINES) : insert_line]
        + new_str_lines
        + file_text_lines[insert_line : insert_line + SNIPPET_LINES]
    )

    new_file_text = "\n".join(new_file_text_lines)
    snippet = "\n".join(snippet_lines)

    _write_file(path, new_file_text)

    success_msg = f"The file {path} has been edited. "
    success_msg += _make_output(
        snippet,
        "a snippet of the edited file",
        max(1, insert_line - SNIPPET_LINES + 1),
    )
    success_msg += "Review the changes and make sure they are as expected (correct indentation, no duplicate lines, etc). Edit the file again if necessary."
    return CLIResult(output=success_msg)


async def extract_diff(
    project_dir: Path | str | None = None,
) -> CLIResult | ToolErrorInfo:
    """
    Extract the diff of the current state of the repository.

    Returns:
        CLIResult: The result of the diff extraction, containing the output or error.
    """
    assert _project_dir is not None, "Project directory must be initialized first."
    project_dir = project_dir or _project_dir

    logger.info(
        f"[Tool] Invoked edit_tool `extract_diff`. Extracting a patch from {project_dir} (type: {type(project_dir)})"
    )

    if (
        guard_rail_tool_error := useagent_guard_rail(
            project_dir,
            supplied_arguments=[
                ArgumentEntry("project_dir", str(project_dir)),
            ],
        )
    ) is not None:
        return guard_rail_tool_error

    with cd(project_dir):
        # Git Add is necessary to see changes to newly created files with the git diff
        await run("git add .")
        _, cached_out, stderr_1 = await run("git diff --cached")
        _, working_out, stderr_2 = await run("git diff")
        stdout = cached_out + working_out

        if stderr_1 or stderr_2:
            return ToolErrorInfo(
                message=f"Failed to extract diff: {stderr_1 + stderr_2}",
                supplied_arguments=[
                    ArgumentEntry("project_dir", str(project_dir)),
                ],
            )

        if not stdout or not stdout.strip():
            logger.debug("[Tool] edit_tool `extract_diff`: Received empty Diff")
            return CLIResult(output="No changes detected in the repository.")
        logger.debug(
            f"[Tool] edit_tool `extract_diff`: Received {stdout[:25]} ... from {project_dir}"
        )
        return CLIResult(output=f"Here's the diff of the current state:\n{stdout}")


async def read_file_as_diff(path_to_file: Path | str) -> CLIResult | ToolErrorInfo:
    """
    Reports a file at a given `path_to_file` as a git diff that would create this file (if it was absent).
    Does not take any git history of the file into account, just it's current state.


    Args:
        path_to_file (Path | str): The path to the file.

    Returns:
        CLIResult: The git diff that would create the file.
    """

    logger.info(
        f"[Tool] Invoked edit_tool `read_file_as_diff`. Extracting a file as patch from {path_to_file} (type: {type(path_to_file)})"
    )
    supplied_arguments = [ArgumentEntry("path_to_file", str(path_to_file))]

    path = (
        _make_path_absolute(path_to_file)
        if isinstance(path_to_file, str)
        else path_to_file.absolute()
    )

    if not path.exists():
        return ToolErrorInfo(
            message=f"File at {path_to_file} does not exist.",
            supplied_arguments=supplied_arguments,
        )
    if path.is_dir():
        return ToolErrorInfo(
            message=f"{path_to_file} points to a directory. Only (single) files are supported",
            supplied_arguments=supplied_arguments,
        )

    command = f"git diff --binary -- /dev/null {str(path)}"
    _, stdout, stderr = await run(command)

    if stderr:
        return ToolErrorInfo(
            message=f"Failed to make a patch from file: {stderr}",
            supplied_arguments=supplied_arguments,
        )

    return CLIResult(
        output=f"This is a patch would newly create the file at {str(path)}:\n{stdout}"
    )


def __reset_project_dir():
    """
    This project is only used for tests and testing purposes.
    Otherwise, with our `init_edit_tools` we introduce some side-effects that make tests a bit flaky.
    """
    global _project_dir
    _project_dir = None
