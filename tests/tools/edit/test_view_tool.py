import pytest
from pathlib import Path
from useagent.tools.edit import view
from useagent.tools.base import ToolError,CLIResult

pytestmark = pytest.mark.asyncio


async def test_view_file_entire_content(tmp_path: Path):
    file = tmp_path / "example.txt"
    content = "line1\nline2\nline3"
    file.write_text(content)

    result = await view(str(file))
    assert isinstance(result, CLIResult)
    assert "line1" in result.output
    assert "line3" in result.output


async def test_view_file_with_valid_range(tmp_path: Path):
    file = tmp_path / "example.txt"
    file.write_text("a\nb\nc\nd\ne")

    result = await view(str(file), [2, 4])
    assert "b" in result.output
    assert "d" in result.output
    assert "a" not in result.output
    assert "e" not in result.output


async def test_view_file_with_open_ended_range(tmp_path: Path):
    file = tmp_path / "example.txt"
    file.write_text("a\nb\nc\nd")

    result = await view(str(file), [3, -1])
    assert "c" in result.output
    assert "d" in result.output
    assert "a" not in result.output


async def test_view_file_invalid_range_length(tmp_path: Path):
    file = tmp_path / "bad_range.txt"
    file.write_text("x\ny\nz")

    with pytest.raises(ToolError, match="Invalid `view_range`"):
        await view(str(file), [1])


async def test_view_file_invalid_range_order(tmp_path: Path):
    file = tmp_path / "bad_order.txt"
    file.write_text("x\ny\nz")

    with pytest.raises(ToolError, match="second element.*should be larger or equal"):
        await view(str(file), [3, 1])


async def test_view_file_invalid_range_start(tmp_path: Path):
    file = tmp_path / "bad_start.txt"
    file.write_text("x\ny\nz")

    with pytest.raises(ToolError, match="should be within the range of lines of the file"):
        await view(str(file), [0, 2])


async def test_view_file_invalid_range_end(tmp_path: Path):
    file = tmp_path / "bad_end.txt"
    file.write_text("x\ny\nz")

    with pytest.raises(ToolError, match="should be smaller than the number of lines"):
        await view(str(file), [1, 10])


async def test_view_directory_listing(tmp_path: Path):
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "file1.txt").write_text("hello")
    (subdir / "file2.txt").write_text("world")

    result = await view(str(tmp_path))
    assert isinstance(result, CLIResult)
    assert "file1.txt" in result.output
    assert "file2.txt" in result.output


async def test_view_directory_with_range_fails(tmp_path: Path):
    tmp_path.mkdir()

    with pytest.raises(ToolError, match="`view_range` parameter is not allowed"):
        await view(str(tmp_path), [1, 2])
