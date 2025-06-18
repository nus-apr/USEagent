import pytest
from pathlib import Path
from useagent.tools.edit import create
from useagent.tools.base import ToolError, ToolResult

@pytest.mark.asyncio
async def test_create_file_success(tmp_path: Path):
    file = tmp_path / "new_file.txt"
    content = "This is a new file."

    result = await create(str(file), content)

    assert isinstance(result, ToolResult)
    assert "File created successfully" in result.output
    assert file.exists()
    assert file.read_text() == content


@pytest.mark.asyncio
async def test_create_file_already_exists(tmp_path: Path):
    file = tmp_path / "existing.txt"
    file.write_text("Existing content")

    with pytest.raises(ToolError, match="File already exists"):
        await create(str(file), "New content")


@pytest.mark.asyncio
async def test_create_empty_file(tmp_path: Path):
    file = tmp_path / "empty.txt"
    result = await create(str(file), "")

    assert isinstance(result, ToolResult)
    assert "File created successfully" in result.output
    assert file.exists()
    assert file.read_text() == ""


@pytest.mark.asyncio
async def test_create_file_nested_directory(tmp_path: Path):
    nested_dir = tmp_path / "dir1" / "dir2"
    nested_dir.mkdir(parents=True)
    file = nested_dir / "nested.txt"
    content = "Nested file content"

    result = await create(str(file), content)

    assert isinstance(result, ToolResult)
    assert "File created successfully" in result.output
    assert file.exists()
    assert file.read_text() == content


@pytest.mark.asyncio
async def test_create_file_path_is_directory(tmp_path: Path):
    dir_path = tmp_path / "not_a_file"
    dir_path.mkdir()

    with pytest.raises(ToolError):
        await create(str(dir_path), "This should fail")
