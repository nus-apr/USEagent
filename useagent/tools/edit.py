import os
from pathlib import Path
from loguru import logger

from useagent.tools.base import CLIResult, ToolError, ToolResult
from useagent.tools.run import maybe_truncate, run
from useagent.utils import cd


SNIPPET_LINES: int = 4


_project_dir: Path = None


def init_edit_tools(project_dir: str):
    if not project_dir or (isinstance(project_dir,str) and not (project_dir.strip())):
        raise ValueError("Cannot initialize edit-tool without a valid project dir - was given `None` or empty string.")
    global _project_dir
    _project_dir = Path(project_dir)


def _make_path_absolute(path: str) -> Path:
    if os.path.isabs(path):
        return Path(path)
    return _project_dir / path


def _read_file(path: Path):
    """Read the content of a file from a given path; raise a ToolError if an error occurs."""
    try:
        return path.read_text()
    except Exception as e:
        raise ToolError(f"Ran into {e} while trying to read {path}") from None


def _write_file(path: Path, file: str):
    """Write the content of a file to a given path; raise a ToolError if an error occurs."""
    try:
        path.write_text(file)
    except Exception as e:
        raise ToolError(f"Ran into {e} while trying to write to {path}") from None


def _make_output(
    file_content: str,
    file_descriptor: str,
    init_line: int = 1,
    expand_tabs: bool = True,
):
    """Generate output for the CLI based on the content of a file."""
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


# TODO: change all raised exceptions to returned errors


async def view(file_path: str, view_range: list[int] | None = None):
    """
    View the content of a file or directory at the specified path.
    If view_range is provided, only the specified lines will be returned.

    Args:
        file_path (str): The relative path to the file or directory.
        view_range (list[int] | None): A list of two integers specifying the range of lines to view. Only applicable to files, not directories.

    Returns:
        ToolResult: The result of the view operation, containing the output and a short header summarizing the used command.
    """
    logger.info(f"[Tool] Invoked edit_tool `view`. Viewing {file_path}, range {view_range}")

    path = _make_path_absolute(file_path)

    if not path.exists():
        raise ToolError(f"Filepath {file_path} does not exist.")
    if path.is_dir():
        if view_range:
            raise ToolError(
                "The `view_range` parameter is not allowed when `path` points to a directory."
            )

        _, stdout, stderr = await run(rf"find {path} -maxdepth 2 -not -path '*/\.*'")
        if not stderr:
            stdout = f"Here's the files and directories up to 2 levels deep in {path}, excluding hidden items:\n{stdout}\n"
        return CLIResult(output=stdout, error=stderr)

    file_content = _read_file(path)
    init_line = 1
    if view_range:
        if len(view_range) != 2 or not all(isinstance(i, int) for i in view_range):
            raise ToolError(
                "Invalid `view_range`. It should be a list of two integers."
            )
        file_lines = file_content.split("\n")
        n_lines_file = len(file_lines)
        init_line, final_line = view_range
        if init_line < 1 or init_line > n_lines_file:
            raise ToolError(
                f"Invalid `view_range`: {view_range}. Its first element `{init_line}` should be within the range of lines of the file: {[1, n_lines_file]}"
            )
        if final_line > n_lines_file:
            raise ToolError(
                f"Invalid `view_range`: {view_range}. Its second element `{final_line}` should be smaller than the number of lines in the file: `{n_lines_file}`"
            )
        if final_line != -1 and final_line < init_line:
            raise ToolError(
                f"Invalid `view_range`: {view_range}. Its second element `{final_line}` should be larger or equal than its first `{init_line}`"
            )

        if final_line == -1:
            file_content = "\n".join(file_lines[init_line - 1 :])
        else:
            file_content = "\n".join(file_lines[init_line - 1 : final_line])

    return CLIResult(output=_make_output(file_content, str(path), init_line=init_line))


async def create(file_path: str, file_text: str):
    """
    Create a new file at the specified path with the given text content.
    Text content can empty. 
    Path must be a valid path that does not exist, path cannot be empty or 'None'.

    Args:
        file_path (str): The path where the new file will be created.
        file_text (str): The text content to write into the new file.

    Returns:
        ToolResult: The result of the create operation, indicating success or failure.
    """
    logger.info(f"[Tool] Invoked edit_tool `create`. Creating {file_path}, content preview: {file_text[:15]} ...")

    if not file_path or not file_path.strip():
        raise ToolError("Received an None or Empty file_path argument.")

    path = _make_path_absolute(file_path)

    if path.exists():
        raise ToolError(
            f"File already exists at: {path}. Cannot overwrite files using command `create`."
        )

    _write_file(path, file_text)
    return ToolResult(output=f"File created successfully at: {file_path}")


async def str_replace(file_path: str, old_str: str, new_str: str):
    """
    Replace old_str with new_str in the content of the file at the specified path.

    Args:
        file_path (str): The path to the file where the replacement will occur.
        old_str (str): The string to be replaced.
        new_str (str): The string to replace with.

    Returns:
        ToolResult: The result of the str_replace operation, containing the output or error.
    """
    logger.info(f"[Tool] Invoked edit_tool `str_replace`. Replacing {old_str} for {new_str} in {file_path}")

    # Read the file content
    path = _make_path_absolute(file_path)
    
    if not path.exists():
        raise ToolError(f"Filepath {file_path} does not exist, it has to be created first. `str_replace` only works for existing files.")
    if path.exists() and path.is_dir():
        raise ToolError(f"Filepath {file_path} is a directory - `str_replace` can only be applied to files.")

    file_content = _read_file(path).expandtabs()
    old_str = old_str.expandtabs()
    new_str = new_str.expandtabs()

    # Check if old_str is unique in the file
    occurrences = file_content.count(old_str)
    if occurrences == 0:
        raise ToolError(
            f"No replacement was performed, old_str `{old_str}` did not appear verbatim in {path}."
        )
    elif occurrences > 1:
        file_content_lines = file_content.split("\n")
        lines = [
            idx + 1 for idx, line in enumerate(file_content_lines) if old_str in line
        ]
        raise ToolError(
            f"No replacement was performed. Multiple occurrences of old_str `{old_str}` in lines {lines}. Please ensure it is unique"
        )

    # Replace old_str with new_str
    new_file_content = file_content.replace(old_str, new_str)

    # Write the new content to the file
    _write_file(path, new_file_content)

    # Create a snippet of the edited section
    replacement_line = file_content.split(old_str)[0].count("\n")
    start_line = max(0, replacement_line - SNIPPET_LINES)
    end_line = replacement_line + SNIPPET_LINES + new_str.count("\n")
    snippet = "\n".join(new_file_content.split("\n")[start_line : end_line + 1])

    # Prepare the success message
    success_msg = f"The file {path} has been edited. "
    success_msg += _make_output(snippet, f"a snippet of {path}", start_line + 1)
    success_msg += "Review the changes and make sure they are as expected. Edit the file again if necessary."

    return CLIResult(output=success_msg)


async def insert(file_path: str, insert_line: int, new_str: str):
    """
    Insert new_str at the specified line in the file at the given path.

    Args:
        file_path (str): The path to the file where the insertion will occur.
        insert_line (int): The line number at which to insert new_str (0-indexed).
        new_str (str): The string to insert into the file.

    Returns:
        ToolResult: The result of the insert operation, containing the output or error.
    """
    logger.info(f"[Tool] Invoked edit_tool `insert`. Inserting {new_str} at L{insert_line} in {file_path}")

    path = _make_path_absolute(file_path)

    if not path.exists():
        raise ToolError(f"Filepath {file_path} does not exist, it has to be created first. `insert` only works for existing files.")
    if path.exists() and path.is_dir():
        raise ToolError(f"Filepath {file_path} is a directory - `insert` can only be applied to files.")

    file_text = _read_file(path).expandtabs()
    new_str = new_str.expandtabs()
    file_text_lines = file_text.split("\n")
    n_lines_file = len(file_text_lines)

    if insert_line < 0 or insert_line > n_lines_file:
        raise ToolError(
            f"Invalid `insert_line` parameter: {insert_line}. It should be within the range of lines of the file: {[0, n_lines_file]}"
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


async def extract_diff(project_dir: Path | str = None):
    """
    Extract the diff of the current state of the repository.

    Returns:
        ToolResult: The result of the diff extraction, containing the output or error.
    """
    project_dir = project_dir or _project_dir
    logger.info(f"[Tool] Invoked edit_tool `extract_diff`. Extracting a patch from {project_dir} (type: {type(project_dir)})")

    with cd(project_dir):
        await run("git add .") # Git Add is necessary to see changes to newly created files
        _, cached_out, stderr_1 = await run("git diff --cached")
        _, working_out, stderr_2 = await run("git diff")
        stdout = cached_out + working_out

        if stderr_1 or stderr_2:
            raise ToolError(f"Failed to extract diff: {stderr_1 + stderr_2}")
        if not stdout or not stdout.strip():
            logger.debug(f"[Tool] edit_tool `extract_diff`: Received empty Diff")
            return ToolResult(output="No changes detected in the repository.")
        logger.debug(f"[Tool] edit_tool `extract_diff`: Received {stdout[:25]} ... from {project_dir}")
        return ToolResult(output=f"Here's the diff of the current state:\n{stdout}")
