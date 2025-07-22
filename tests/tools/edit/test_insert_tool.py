from pathlib import Path

import pytest

from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo
from useagent.tools.edit import init_edit_tools, insert


@pytest.mark.tool
@pytest.mark.asyncio
async def test_insert_basic_insertion(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "basic.txt"
    file.write_text("line1\nline2\nline3")

    result = await insert(str(file), 1, "inserted")

    assert isinstance(result, CLIResult)
    content = file.read_text().splitlines()
    assert content == ["line1", "inserted", "line2", "line3"]
    assert "inserted" in result.output


@pytest.mark.tool
@pytest.mark.asyncio
async def test_insert_multiline_insertion(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "multi.txt"
    file.write_text("line1\nline2")

    result = await insert(str(file), 1, "new1\nnew2")

    assert isinstance(result, CLIResult)
    content = file.read_text().splitlines()
    assert content == ["line1", "new1", "new2", "line2"]
    assert "new1" in result.output
    assert "new2" in result.output


@pytest.mark.tool
@pytest.mark.asyncio
async def test_insert_top_of_file(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "top.txt"
    file.write_text("original line")

    result = await insert(str(file), 0, "header")
    assert isinstance(result, CLIResult)
    assert file.read_text().splitlines()[0] == "header"


@pytest.mark.tool
@pytest.mark.asyncio
async def test_insert_bottom_of_file(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "bottom.txt"
    file.write_text("line1\nline2")

    result = await insert(str(file), 2, "appended")

    assert isinstance(result, CLIResult)
    assert file.read_text().splitlines()[-1] == "appended"


@pytest.mark.tool
@pytest.mark.asyncio
async def test_insert_invalid_negative_line(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "negative.txt"
    file.write_text("line1\nline2")

    result = await insert(str(file), -1, "invalid")

    assert isinstance(result, ToolErrorInfo)
    assert result.tool == "insert"
    assert "invalid" in result.message.lower()


@pytest.mark.tool
@pytest.mark.asyncio
async def test_insert_invalid_too_large_line(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "toolarge.txt"
    file.write_text("line1\nline2")

    result = await insert(str(file), 3, "invalid")

    assert isinstance(result, ToolErrorInfo)
    assert result.tool == "insert"
    assert "invalid" in result.message.lower()


@pytest.mark.tool
@pytest.mark.asyncio
async def test_insert_tabs_fill_whitespace_up_to_fixed_point(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "tabs.txt"
    file.write_text("line1")

    result = await insert(str(file), 1, "a\tb")
    assert isinstance(result, CLIResult)
    assert "a       b" in file.read_text()


@pytest.mark.tool
@pytest.mark.asyncio
async def test_insert_tabs_fill_whitespace_up_to_fixed_point_longer_initial_string_will_add_less_whitespace(
    tmp_path: Path,
):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "tabs.txt"
    file.write_text("line1")

    result = await insert(str(file), 1, "app\tb")
    assert isinstance(result, CLIResult)
    assert "app     b" in file.read_text()
