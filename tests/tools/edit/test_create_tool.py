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


@pytest.mark.tool
@pytest.mark.asyncio
async def test_create_large_file_should_exist(tmp_path: Path):
    file = tmp_path / "huge.txt"
    lines: int = 2000
    content: str = "foo\n".join(f"line {i}" for i in range(lines))
    init_edit_tools(str(tmp_path))

    result = await create(str(file), content)

    assert isinstance(result, CLIResult)
    assert file.exists()
    # optional sanity check
    assert file.read_text().count("foo\n") + 1 == lines


@pytest.mark.tool
@pytest.mark.asyncio
async def test_create_shell_file_should_be_executable(tmp_path: Path):
    file = tmp_path / "script.sh"
    content: str = """#!/bin/bash
echo "Hello World"
FOO=bar
echo "Value of FOO is $FOO"
"""
    init_edit_tools(str(tmp_path))

    result = await create(str(file), content)

    assert isinstance(result, CLIResult)
    assert file.exists()
    text = file.read_text()
    assert "Hello World" in text
    assert "FOO=bar" in text


@pytest.mark.tool
@pytest.mark.asyncio
async def test_create_markdown_file_should_contain_code_block(tmp_path: Path):
    file = tmp_path / "instructions.md"
    content: str = """# Project Setup
    Follow these steps:

    1. Create a virtual environment
    2. Install dependencies
    3. Run the application

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    python main.py

    ```
    """
    init_edit_tools(str(tmp_path))
    result = await create(str(file), content)

    assert isinstance(result, CLIResult)
    assert file.exists()
    text = file.read_text()
    assert text.startswith("# Project Setup")
    assert "```bash" in text


@pytest.mark.tool
@pytest.mark.asyncio
async def test_create_shell_file_with_encoded_newlines(tmp_path: Path):
    file = tmp_path / "encoded_script.sh"
    content: str = '#!/bin/bash\necho "Hello Encoded"\nVAR=42\necho "VAR is $VAR"\n'
    init_edit_tools(str(tmp_path))

    result = await create(str(file), content)

    assert isinstance(result, CLIResult)
    assert file.exists()
    text = file.read_text()
    assert "Hello Encoded" in text
    assert "VAR=42" in text
    assert len(text.splitlines()) > 1
