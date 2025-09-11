import os
import subprocess
from pathlib import Path

import pytest

from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo
from useagent.tools.git import extract_diff

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
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=repo_path, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True
    )

    file = repo_path / "test.txt"
    file.write_text("original content\n")
    subprocess.run(["git", "add", "test.txt"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True)

    # Modify the file to produce a diff
    file.write_text("original content\nnew line\n")

    return file


def _init_git_repo_without_content(repo_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=repo_path, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True
    )


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_real_changes(tmp_path):
    _setup_git_repo_with_change(tmp_path)

    result = await extract_diff(project_dir=tmp_path)

    assert isinstance(result, CLIResult)
    assert "diff --git" in result.output
    assert "+new line" in result.output


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_no_changes_after_commit(tmp_path):
    _setup_git_repo_with_change(tmp_path)
    os.system(f"cd {tmp_path} && git add . && git commit -m 'Apply change'")

    result = await extract_diff(project_dir=tmp_path)

    assert isinstance(result, CLIResult)
    assert result.output.strip() == "No changes detected in the repository."


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
    (tmp_path / ".gitignore").write_text("ignored.txt\n")
    (tmp_path / "tracked.txt").write_text("t\n")

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True
    )
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", ".gitignore"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)

    # Now create ignored file
    (tmp_path / "ignored.txt").write_text("ignore me\n")
    (tmp_path / "tracked.txt").write_text("t2\n")

    result = await extract_diff(project_dir=tmp_path)
    assert "ignored.txt" not in result.output
    assert "tracked.txt" in result.output


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


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_untracked_file_is_not_included(tmp_path: Path):
    # DevNote:
    # This tests for the case that a completely new file was added, not a change but a `create`
    # These do NOT appear in a git diff, unless there was a git add (they were not added to the index)
    (tmp_path / "tracked.txt").write_text("initial\n")

    # Initialize repo and commit
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True
    )
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)

    # Create untracked file
    (tmp_path / "untracked.txt").write_text("should not appear\n")

    result = await extract_diff(project_dir=tmp_path)
    assert isinstance(result, CLIResult)
    assert "untracked.txt" in result.output
    assert not result.output.strip() == "No changes detected in the repository."


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_tracked_file_change_included_untracked_ignored(
    tmp_path: Path,
):
    # DevNote:
    # This tests for the case that a completely new file was added, not a change but a `create`
    # These do NOT appear in a git diff, unless there was a git add (they were not added to the index)
    (tmp_path / "a.txt").write_text("a\n")
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True
    )
    subprocess.run(["git", "add", "a.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)

    # Modify tracked file and add untracked file
    (tmp_path / "a.txt").write_text("a changed\n")
    (tmp_path / "new.txt").write_text("untracked\n")

    result = await extract_diff(project_dir=tmp_path)
    assert "diff --git a/a.txt" in result.output
    assert "new.txt" in result.output


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_issue_26_extract_diff_handles_non_utf8_text_file_change_should_not_crash(
    tmp_path: Path,
):
    _init_git_repo_without_content(tmp_path)
    p = tmp_path / "latin1.txt"
    p.write_bytes(b"hola\xa0mundo\n")
    subprocess.run(["git", "add", p.name], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "add latin1"], cwd=tmp_path, check=True)

    p.write_bytes(b"hola\xa0mundo\ncambio\xa0\n")

    result = await extract_diff(project_dir=tmp_path)
    assert isinstance(result, CLIResult)
    assert result.output.strip()
    assert (
        ("diff --git" in result.output)
        or ("Binary files" in result.output)
        or (p.name in result.output)
    )


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_issue_26_extract_diff_handles_binary_file_change_should_not_crash(
    tmp_path: Path,
):
    _init_git_repo_without_content(tmp_path)
    png = tmp_path / "img.png"
    png.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    subprocess.run(["git", "add", png.name], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "add png"], cwd=tmp_path, check=True)

    data = png.read_bytes()
    png.write_bytes(data[:-1] + bytes([data[-1] ^ 0xFF]))

    result = await extract_diff(project_dir=tmp_path)
    assert isinstance(result, CLIResult)
    assert result.output.strip()
    assert (
        ("GIT binary patch" in result.output)
        or ("Binary files" in result.output)
        or (png.name in result.output)
    )


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_issue_26_extract_diff_respects_non_utf8_filename_should_not_crash(
    tmp_path: Path,
):
    _init_git_repo_without_content(tmp_path)
    subprocess.run(
        ["git", "config", "core.quotepath", "false"], cwd=tmp_path, check=True
    )

    fname = "über 🧪.txt"
    fpath = tmp_path / fname
    fpath.write_text("hi\n")
    subprocess.run(["git", "add", fname], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "add unicode name"], cwd=tmp_path, check=True
    )

    fpath.write_text("hi\nchanged\n")

    result = await extract_diff(project_dir=tmp_path)
    assert isinstance(result, CLIResult)
    assert "diff --git" in result.output
    assert fname in result.output


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_with_color_enabled_should_not_strip_colors(tmp_path: Path):
    _init_git_repo_without_content(tmp_path)
    subprocess.run(["git", "config", "color.ui", "always"], cwd=tmp_path, check=True)

    p = tmp_path / "a.txt"
    p.write_text("a\n")
    subprocess.run(["git", "add", "a.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)

    p.write_text("a\nb\n")

    result = await extract_diff(project_dir=tmp_path)
    assert isinstance(result, CLIResult)
    assert "diff --git a/a.txt" in result.output
    assert "\x1b[" in result.output  # no ANSI color sequences


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_issue_26_extract_diff_large_hunks_should_not_crash(tmp_path: Path):
    _init_git_repo_without_content(tmp_path)

    big = tmp_path / "big.txt"
    big.write_bytes(b"x" * (2 * 1024 * 1024))
    subprocess.run(["git", "add", big.name], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "add big"], cwd=tmp_path, check=True)

    big.write_bytes(big.read_bytes() + (b"\xa0" * (256 * 1024)) + b"\nmore\n")

    result = await extract_diff(project_dir=tmp_path)
    assert isinstance(result, CLIResult)
    assert result.output.strip()
    assert big.name in result.output


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_issue_41_extract_diff_missing_directory_should_return_tool_error_info(
    tmp_path: Path,
):
    missing = tmp_path / "does_not_exist"
    assert not missing.exists()
    result = await extract_diff(project_dir=missing)
    assert result
    assert isinstance(result, ToolErrorInfo)


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_issue_41_extract_diff_missing_file_should_return_tool_error_info(
    tmp_path: Path,
):
    missing = tmp_path / "does_not_exist.txt"
    assert not missing.exists()
    result = await extract_diff(project_dir=missing)
    assert result
    assert isinstance(result, ToolErrorInfo)
