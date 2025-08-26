from pathlib import Path

import pytest

from useagent.config import ConfigSingleton
from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo
from useagent.tools.edit import init_edit_tools, view


@pytest.mark.tool
@pytest.mark.asyncio
async def test_view_file_entire_content(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "example.txt"
    content = "line1\nline2\nline3"
    file.write_text(content)

    result = await view(str(file))
    assert isinstance(result, CLIResult)
    assert "line1" in result.output
    assert "line3" in result.output


@pytest.mark.tool
@pytest.mark.asyncio
async def test_view_file_has_header(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "example.txt"
    content = "line1\nline2\nline3"
    file.write_text(content)

    result = await view(str(file))
    assert isinstance(result, CLIResult)
    assert "Here's" in result.output
    assert "cat -n" in result.output
    assert 4 == len(result.output.splitlines())


@pytest.mark.asyncio
async def test_view_file_with_valid_range(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "example.txt"
    file.write_text("a\nb\nc\nd\ne")

    result = await view(str(file), [2, 4])
    output_no_header = "\n".join((result.output.splitlines())[1:])

    assert "b" in output_no_header
    assert "d" in output_no_header
    assert "a" not in output_no_header
    assert "e" not in output_no_header


@pytest.mark.asyncio
async def test_view_file_with_open_ended_range(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "example.txt"
    file.write_text("a\nb\nc\nd")

    result = await view(str(file), [3, -1])
    output_no_header = "\n".join((result.output.splitlines())[1:])

    assert "c" in output_no_header
    assert "d" in output_no_header
    assert "a" not in output_no_header


@pytest.mark.asyncio
async def test_view_file_invalid_range_length(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "bad_range.txt"
    file.write_text("x\ny\nz")

    result = await view(str(file), [1])

    assert isinstance(result, ToolErrorInfo)
    assert "invalid" in result.message.lower()


@pytest.mark.asyncio
async def test_view_file_invalid_range_order(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "bad_order.txt"
    file.write_text("x\ny\nz")

    result = await view(str(file), [3, 1])

    assert isinstance(result, ToolErrorInfo)
    assert (
        "order" in result.message.lower() or "second element" in result.message.lower()
    )


@pytest.mark.asyncio
async def test_view_file_invalid_range_start(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "bad_start.txt"
    file.write_text("x\ny\nz")

    result = await view(str(file), [0, 2])

    assert isinstance(result, ToolErrorInfo)
    assert "range" in result.message.lower()


@pytest.mark.asyncio
async def test_view_file_invalid_range_end(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "bad_end.txt"
    file.write_text("x\ny\nz")

    result = await view(str(file), [1, 10])

    assert isinstance(result, ToolErrorInfo)
    assert "range" in result.message.lower() or "too large" in result.message.lower()


@pytest.mark.asyncio
async def test_view_directory_listing(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "file1.txt").write_text("hello")
    (subdir / "file2.txt").write_text("world")

    result = await view(str(tmp_path))
    assert isinstance(result, CLIResult)
    assert "file1.txt" in result.output
    assert "file2.txt" in result.output


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_view_file_for_very_long_file_should_be_shortened(
    tmp_path: Path, monkeypatch
):
    # Issue #30 - long files should be shorted
    ConfigSingleton.reset()
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    ConfigSingleton.init("google-gla:gemini-2.5-flash")
    ConfigSingleton.config.context_window_limits["google-gla:gemini-2.5-flash"] = 150
    init_edit_tools(str(tmp_path))

    file = tmp_path / "example.txt"
    content = "very long text\n" * 250
    file.write_text(content)

    result = await view(str(file))
    assert isinstance(result, CLIResult)

    assert "[[ ... Cut to fit Context Window ... ]]" in result.output

    ConfigSingleton.reset()


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_view_file_for_short_file_should_not_be_shortened(
    tmp_path: Path, monkeypatch
):
    # Issue #30 - short files are ok
    ConfigSingleton.reset()
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    ConfigSingleton.init("google-gla:gemini-2.5-flash")
    ConfigSingleton.config.context_window_limits["google-gla:gemini-2.5-flash"] = 10000
    init_edit_tools(str(tmp_path))

    file = tmp_path / "example.txt"
    content = "short text\n" * 25
    file.write_text(content)

    result = await view(str(file))
    assert isinstance(result, CLIResult)
    assert "[[ ... Cut to fit Context Window ... ]]" not in result.output

    ConfigSingleton.reset()
