from pathlib import Path

import pytest

from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo
from useagent.tools.edit import init_edit_tools, replace_file


@pytest.mark.tool
def test_replace_file_success_should_replace_file_content(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "target.txt"
    file.write_text("old content")

    result = replace_file("new content", str(file))

    assert isinstance(result, CLIResult)
    assert "File replaced successfully" in result.output
    assert file.exists()
    assert file.read_text() == "new content"


@pytest.mark.tool
def test_replace_file_nonexistent_path_should_return_tool_error_info(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "missing.txt"

    result = replace_file("content", str(file))

    assert isinstance(result, ToolErrorInfo)
    assert "does not exist" in result.message


@pytest.mark.tool
def test_replace_file_path_is_directory_should_return_tool_error_info(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    dir_path = tmp_path / "a_dir"
    dir_path.mkdir()

    result = replace_file("content", str(dir_path))

    assert isinstance(result, ToolErrorInfo)
    assert "directory" in result.message.lower()


@pytest.mark.tool
def test_replace_file_empty_string_content_should_not_change_file(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "empty_target.txt"
    file.write_text("old")

    result = replace_file("", str(file))

    assert isinstance(result, ToolErrorInfo)
    assert "empty" in result.message.lower()


@pytest.mark.tool
def test_replace_file_whitespace_only_content_should_not_replace(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "ws_target.txt"
    file.write_text("old")

    result = replace_file("   \n\t  ", str(file))

    assert isinstance(result, ToolErrorInfo)
    assert "empty" in result.message.lower()


@pytest.mark.tool
def test_replace_file_with_non_utf8_string_should_return_toolerror(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "binary.txt"
    file.write_text("old")

    # Create a string with a surrogate that cannot be encoded to UTF-8
    bad_str = "abc\udcffdef"

    result = replace_file(bad_str, str(file))

    assert isinstance(result, ToolErrorInfo)
    assert "utf-8" in result.message.lower()
    # Ensure the file was not replaced
    assert file.read_text() == "old"


@pytest.mark.tool
def test_replace_file_string_with_explicit_newlines_should_preserve_lines(
    tmp_path: Path,
):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "with_newlines.txt"
    file.write_text("old")

    new_content = "line1\nline2\nline3"
    result = replace_file(new_content, str(file))

    assert isinstance(result, CLIResult)
    assert file.exists()
    content_lines = file.read_text().splitlines()
    assert len(content_lines) == 3
    assert content_lines == ["line1", "line2", "line3"]


@pytest.mark.tool
def test_replace_file_multiline_python_string_should_preserve_lines(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "multiline.txt"
    file.write_text("old")

    new_content = """first line
second line
third line"""
    result = replace_file(new_content, str(file))

    assert isinstance(result, CLIResult)
    assert file.exists()
    content_lines = file.read_text().splitlines()
    assert len(content_lines) == 3
    assert content_lines == ["first line", "second line", "third line"]


@pytest.mark.tool
def test_replace_file_with_absolute_path_str(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "abs_str.txt"
    file.write_text("old")

    result = replace_file("new", str(file.absolute()))

    assert isinstance(result, CLIResult)
    assert file.read_text() == "new"


@pytest.mark.tool
def test_replace_file_with_relative_path_str(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "rel_str.txt"
    file.write_text("old")

    rel_path = file.relative_to(tmp_path)
    result = replace_file("new", str(rel_path))

    assert isinstance(result, CLIResult)
    assert file.read_text() == "new"


@pytest.mark.tool
def test_replace_file_with_absolute_path_pathlib(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "abs_path.txt"
    file.write_text("old")

    result = replace_file("new", file.absolute())

    assert isinstance(result, CLIResult)
    assert file.read_text() == "new"


@pytest.mark.tool
def test_replace_file_with_relative_path_pathlib(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "rel_path.txt"
    file.write_text("old")

    rel_path = file.relative_to(tmp_path)
    result = replace_file("new", rel_path)

    assert isinstance(result, CLIResult)
    assert file.read_text() == "new"
