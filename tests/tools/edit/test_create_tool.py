from pathlib import Path

import pytest

from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo
from useagent.tools.edit import create, init_edit_tools


@pytest.mark.tool
@pytest.mark.asyncio
async def test_create_file_success(tmp_path: Path):
    file = tmp_path / "new_file.txt"
    content = "This is a new file."
    init_edit_tools(str(tmp_path))

    result = await create(str(file), content)

    assert isinstance(result, CLIResult)
    assert "File created successfully" in result.output
    assert file.exists()
    assert file.read_text() == content


@pytest.mark.tool
@pytest.mark.asyncio
async def test_create_file_already_exists(tmp_path: Path):
    file = tmp_path / "existing.txt"
    file.write_text("Existing content")
    init_edit_tools(str(tmp_path))

    result = await create(str(file), "New content")

    assert isinstance(result, ToolErrorInfo)
    assert "File already exists" in result.message


@pytest.mark.tool
@pytest.mark.asyncio
async def test_create_empty_file(tmp_path: Path):
    file = tmp_path / "empty.txt"
    init_edit_tools(str(tmp_path))

    result = await create(str(file), "")

    assert isinstance(result, CLIResult)
    assert "File created successfully" in result.output
    assert file.exists()
    assert file.read_text() == ""


@pytest.mark.tool
@pytest.mark.asyncio
async def test_create_file_nested_directory(tmp_path: Path):
    nested_dir = tmp_path / "dir1" / "dir2"
    nested_dir.mkdir(parents=True)
    file = nested_dir / "nested.txt"
    content = "Nested file content"
    init_edit_tools(str(tmp_path))

    result = await create(str(file), content)

    assert isinstance(result, CLIResult)
    assert "File created successfully" in result.output
    assert file.exists()
    assert file.read_text() == content


@pytest.mark.tool
@pytest.mark.asyncio
async def test_create_file_path_is_directory(tmp_path: Path):
    dir_path = tmp_path / "not_a_file"
    dir_path.mkdir()
    init_edit_tools(str(tmp_path))

    result = await create(str(dir_path), "This should fail")

    assert isinstance(result, ToolErrorInfo)
