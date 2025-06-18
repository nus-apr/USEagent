import subprocess
import pytest
import os 

from pathlib import Path

from useagent.tools.edit import extract_diff
from useagent.tools.base import ToolError, ToolResult
import useagent.tools.edit as edit_module


# DevNote:
# These tests will require that Git is installed and working. 
# But given that you are using a git repository right now, that should be fine. 

def _setup_git_repo_with_change(repo_path: Path):
    """
    Initializes a git repository, commits a file, and then edits it to create a diff.

    Returns:
        Path to the modified file.
    """
    subprocess.run(["git", "init"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)

    file = repo_path / "test.txt"
    file.write_text("original content\n")
    subprocess.run(["git", "add", "test.txt"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True)

    # Modify the file to produce a diff
    file.write_text("original content\nnew line\n")

    return file

@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_real_changes(tmp_path):
    _setup_git_repo_with_change(tmp_path)

    result = await extract_diff(project_dir=tmp_path)

    assert isinstance(result, ToolResult)
    assert "diff --git" in result.output
    assert "+new line" in result.output


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_no_changes_after_commit(tmp_path):
    _setup_git_repo_with_change(tmp_path)
    os.system(f"cd {tmp_path} && git add . && git commit -m 'Apply change'")

    result = await extract_diff(project_dir=tmp_path)

    assert isinstance(result, ToolResult)
    assert result.output.strip() == "No changes detected in the repository."


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_git_not_initialized(tmp_path):
    with pytest.raises(ToolError, match="Failed to extract diff"):
        await extract_diff(project_dir=tmp_path)

@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_single_file_edit(tmp_path):
    _setup_git_repo_with_change(tmp_path)
    
    file = tmp_path / "test.txt"
    file.write_text("modified content\nanother line\n")

    result = await extract_diff(project_dir=tmp_path)

    assert "diff --git" in result.output
    assert "+another line" in result.output
    assert "-original content" in result.output or "+modified content" in result.output

@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_respects_gitignore(tmp_path):
    _setup_git_repo_with_change(tmp_path)

    # Create a .gitignore and ignored file
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("ignored.txt\n")

    ignored_file = tmp_path / "ignored.txt"
    ignored_file.write_text("should be ignored\n")

    result = await extract_diff(project_dir=tmp_path)

    assert "ignored.txt" not in result.output
    assert "diff --git" in result.output

@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_multiple_files(tmp_path):
    _setup_git_repo_with_change(tmp_path)

    # Add another tracked file
    other = tmp_path / "other.txt"
    other.write_text("initial\n")
    subprocess.run(["git", "add", "other.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "Add other file"], cwd=tmp_path, check=True)

    # Modify both files
    (tmp_path / "test.txt").write_text("changed\n")
    other.write_text("changed too\n")

    result = await extract_diff(project_dir=tmp_path)

    assert "diff --git a/test.txt" in result.output
    assert "diff --git a/other.txt" in result.output

@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_file_deletion(tmp_path):
    file = _setup_git_repo_with_change(tmp_path)

    file.unlink()

    result = await extract_diff(project_dir=tmp_path)

    assert "diff --git" in result.output
    assert "deleted file mode" in result.output

@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_nested_file(tmp_path):
    _setup_git_repo_with_change(tmp_path)

    # Create nested directory and file
    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    nested_file = nested_dir / "nested.txt"
    nested_file.write_text("inside\n")

    subprocess.run(["git", "add", "nested/nested.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "Add nested file"], cwd=tmp_path, check=True)

    # Modify it
    nested_file.write_text("modified\n")

    result = await extract_diff(project_dir=tmp_path)

    assert "diff --git a/nested/nested.txt" in result.output
    assert "+modified" in result.output
