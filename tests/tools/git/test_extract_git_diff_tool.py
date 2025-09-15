import os
import stat
import subprocess
from pathlib import Path

import pytest

from useagent.pydantic_models.artifacts.git.diff import DiffEntry
from useagent.pydantic_models.task_state import TaskState
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo
from useagent.state.git_repo import GitRepository
from useagent.tasks.test_task import TestTask
from useagent.tools.git import _extract_diff, extract_diff

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


def _init_repo_with_tracked(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True
    )
    (tmp_path / "tracked.txt").write_text("t\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)


def _maybe_write_dotignore(tmp_path: Path, ignore: bool) -> None:
    if not ignore:
        return
    (tmp_path / ".gitignore").write_text(
        "**/.*\n" "!.gitignore\n" "!.gitattributes\n" "!.gitmodules\n"
    )
    subprocess.run(["git", "add", ".gitignore"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "add ignore"], cwd=tmp_path, check=True)


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_real_changes(tmp_path):
    _setup_git_repo_with_change(tmp_path)

    result = await _extract_diff(project_dir=tmp_path)

    assert isinstance(result, DiffEntry)
    assert "diff --git" in result.diff_content
    assert "+new line" in result.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_no_changes_after_commit(tmp_path):
    _setup_git_repo_with_change(tmp_path)
    os.system(f"cd {tmp_path} && git add . && git commit -m 'Apply change'")

    result = await _extract_diff(project_dir=tmp_path)

    assert not isinstance(result, DiffEntry)


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_single_file_edit(tmp_path):
    _setup_git_repo_with_change(tmp_path)

    file = tmp_path / "test.txt"
    file.write_text("modified content\nanother line\n")

    result = await _extract_diff(project_dir=tmp_path)

    assert "diff --git" in result.diff_content
    assert "+another line" in result.diff_content
    assert (
        "-original content" in result.diff_content
        or "+modified content" in result.diff_content
    )


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_respects_gitignore(tmp_path):
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

    result = await _extract_diff(project_dir=tmp_path)
    assert "ignored.txt" not in result.diff_content
    assert "tracked.txt" in result.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_multiple_files(tmp_path):
    _setup_git_repo_with_change(tmp_path)

    # Add another tracked file
    other = tmp_path / "other.txt"
    other.write_text("initial\n")
    subprocess.run(["git", "add", "other.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "Add other file"], cwd=tmp_path, check=True)

    # Modify both files
    (tmp_path / "test.txt").write_text("changed\n")
    other.write_text("changed too\n")

    result = await _extract_diff(project_dir=tmp_path)

    assert "diff --git a/test.txt" in result.diff_content
    assert "diff --git a/other.txt" in result.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_file_deletion(tmp_path):
    file = _setup_git_repo_with_change(tmp_path)

    file.unlink()

    result = await _extract_diff(project_dir=tmp_path)

    assert "diff --git" in result.diff_content
    assert "deleted file mode" in result.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_nested_file(tmp_path):
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

    result = await _extract_diff(project_dir=tmp_path)

    assert "diff --git a/nested/nested.txt" in result.diff_content
    assert "+modified" in result.diff_content


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_untracked_file_is_not_included(tmp_path: Path):
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

    result = await _extract_diff(project_dir=tmp_path)
    assert isinstance(result, DiffEntry)
    assert "untracked.txt" in result.diff_content
    assert not result.diff_content.strip() == "No changes detected in the repository."


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_tracked_file_change_included_untracked_ignored(
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

    result = await _extract_diff(project_dir=tmp_path)
    assert "diff --git a/a.txt" in result.diff_content
    assert "new.txt" in result.diff_content


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_issue_26__extract_diff_handles_non_utf8_text_file_change_should_not_crash(
    tmp_path: Path,
):
    _init_git_repo_without_content(tmp_path)
    p = tmp_path / "latin1.txt"
    p.write_bytes(b"hola\xa0mundo\n")
    subprocess.run(["git", "add", p.name], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "add latin1"], cwd=tmp_path, check=True)

    p.write_bytes(b"hola\xa0mundo\ncambio\xa0\n")

    result = await _extract_diff(project_dir=tmp_path)
    assert isinstance(result, DiffEntry)
    assert result.diff_content.strip()
    assert (
        ("diff --git" in result.diff_content)
        or ("Binary files" in result.diff_content)
        or (p.name in result.diff_content)
    )


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_issue_26__extract_diff_handles_binary_file_change_should_raise(
    tmp_path: Path,
):
    # DevNote: we changed this with #44 and currently bytes are not really allowed.
    with pytest.raises(ValueError):
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

        await _extract_diff(project_dir=tmp_path)


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_issue_26__extract_diff_respects_non_utf8_filename_should_not_crash(
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

    result = await _extract_diff(project_dir=tmp_path)
    assert isinstance(result, DiffEntry)
    assert "diff --git" in result.diff_content
    assert fname in result.diff_content


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_issue_26__extract_diff_large_hunks_should_not_crash(tmp_path: Path):
    # DevNote: we changed this with #44 and currently bytes are not really allowed.
    with pytest.raises(ValueError):
        _init_git_repo_without_content(tmp_path)

        big = tmp_path / "big.txt"
        big.write_bytes(b"x" * (2 * 1024 * 1024))
        subprocess.run(["git", "add", big.name], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-m", "add big"], cwd=tmp_path, check=True)

        big.write_bytes(big.read_bytes() + (b"\xa0" * (256 * 1024)) + b"\nmore\n")

        result = await _extract_diff(project_dir=tmp_path)
        assert isinstance(result, DiffEntry)
        assert result.diff_content.strip()
        assert big.name in result.diff_content


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_issue_26__extract_diff_large_hunks_from_text_should_crash_due_to_truncation(
    tmp_path: Path,
):
    # Too large git diffs will get a truncation and contain a <note> etc. about it
    # But that is not a valid git diff then.
    with pytest.raises(ValueError):
        _init_git_repo_without_content(tmp_path)

        big = tmp_path / "big.txt"

        initial = "".join(f"line {i}\n" for i in range(200_000))
        big.write_text(initial, encoding="utf-8")
        subprocess.run(["git", "add", big.name], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-m", "add big"], cwd=tmp_path, check=True)

        modified = (
            "line 0 changed\n"
            + "".join(f"line {i}\n" for i in range(1, 200_000))
            + "".join(f"new {i}\n" for i in range(100_000))
        )
        big.write_text(modified, encoding="utf-8")

        result = await _extract_diff(project_dir=tmp_path)

        result.diff_content


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_issue_41__extract_diff_missing_directory_should_return_tool_error_info(
    tmp_path: Path,
):
    missing = tmp_path / "does_not_exist"
    assert not missing.exists()
    result = await _extract_diff(project_dir=missing)
    assert result
    assert isinstance(result, ToolErrorInfo)


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_issue_41__extract_diff_missing_file_should_return_tool_error_info(
    tmp_path: Path,
):
    missing = tmp_path / "does_not_exist.txt"
    assert not missing.exists()
    result = await _extract_diff(project_dir=missing)
    assert result
    assert isinstance(result, ToolErrorInfo)


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_repo_without_commits_should_list_untracked(tmp_path: Path):
    # DevNote: This got deprecated with Issue #44 because we change the git extraction logic a bit.
    # Now we must have a git commit that was already initialized.
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True
    )

    (tmp_path / "new.txt").write_text("hello\n")

    result = await _extract_diff(project_dir=tmp_path)
    assert not isinstance(result, DiffEntry)


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_rename_should_show_similarity_index(tmp_path: Path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True
    )

    a = tmp_path / "a.txt"
    a.write_text("line1\nline2\nline3\n")
    subprocess.run(["git", "add", "a.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "add a"], cwd=tmp_path, check=True)

    # git mv + small change to keep similarity high
    subprocess.run(["git", "mv", "a.txt", "b.txt"], cwd=tmp_path, check=True)
    b = tmp_path / "b.txt"
    b.write_text("line1\nline2\nline3\nextra\n")

    result = await _extract_diff(project_dir=tmp_path)
    assert (
        "rename from a.txt" in result.diff_content
        or "similarity index" in result.diff_content
    )
    assert (
        "rename to b.txt" in result.diff_content
        or "similarity index" in result.diff_content
    )


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_exec_bit_change_should_show_mode_change(tmp_path: Path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True
    )

    sh = tmp_path / "script.sh"
    sh.write_text("#!/bin/sh\necho hi\n")
    subprocess.run(["git", "add", "script.sh"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "add script"], cwd=tmp_path, check=True)

    os.chmod(sh, os.stat(sh).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    result = await _extract_diff(project_dir=tmp_path)
    # Git shows either old/new mode lines or the 100644 -> 100755 transition
    assert (
        ("new mode 100755" in result.diff_content)
        or ("old mode 100644" in result.diff_content)
        or ("100644" in result.diff_content and "100755" in result.diff_content)
    )


@pytest.mark.tool
@pytest.mark.asyncio
@pytest.mark.skipif(
    not hasattr(os, "symlink"), reason="symlink not supported on this platform"
)
async def test__extract_diff_symlink_target_change_should_be_reported(tmp_path: Path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True
    )

    tgt1 = tmp_path / "target1.txt"
    tgt2 = tmp_path / "target2.txt"
    tgt1.write_text("one\n")
    tgt2.write_text("two\n")

    link = tmp_path / "link.txt"
    os.symlink(tgt1.name, link)  # relative link
    subprocess.run(
        ["git", "add", "target1.txt", "target2.txt", "link.txt"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(["git", "commit", "-m", "add link"], cwd=tmp_path, check=True)

    link.unlink()
    os.symlink(tgt2.name, link)

    result = await _extract_diff(project_dir=tmp_path)
    assert "link.txt" in result.diff_content
    assert "120000" in result.diff_content or "symbolic link" in result.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_whitespace_only_change_behavior_should_show_change(
    tmp_path: Path,
):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True
    )

    p = tmp_path / "ws.txt"
    p.write_text("a b c\n")
    subprocess.run(["git", "add", "ws.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)

    p.write_text("a   b   c\n")  # whitespace-only edit

    result = await _extract_diff(project_dir=tmp_path)
    assert isinstance(result, DiffEntry)
    # Baseline: by default whitespace diffs appear
    assert "diff --git" in result.diff_content
    assert "ws.txt" in result.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_hidden_file_in_root_should_show_when_not_ignored(
    tmp_path: Path,
):
    _init_repo_with_tracked(tmp_path)

    (tmp_path / ".hidden.txt").write_text("secret\n")
    (tmp_path / "tracked.txt").write_text("t2\n")

    result = await _extract_diff(
        project_dir=tmp_path, exclude_hidden_folders_and_files_from_diff=False
    )
    assert isinstance(result, DiffEntry)
    assert "tracked.txt" in result.diff_content
    assert ".hidden.txt" in result.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_hidden_file_in_root_should_not_show_when_ignored(
    tmp_path: Path,
):
    _init_repo_with_tracked(tmp_path)

    (tmp_path / ".gitignore").write_text(
        "**/.*\n!.gitignore\n!.gitattributes\n!.gitmodules\n"
    )
    subprocess.run(["git", "add", ".gitignore"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "add ignore"], cwd=tmp_path, check=True)

    (tmp_path / ".hidden.txt").write_text("secret\n")
    (tmp_path / "tracked.txt").write_text("t2\n")

    result = await _extract_diff(project_dir=tmp_path)
    assert isinstance(result, DiffEntry)
    assert "tracked.txt" in result.diff_content
    assert ".hidden.txt" not in result.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_non_hidden_file_in_hidden_dir_should_show_when_not_ignored(
    tmp_path: Path,
):
    _init_repo_with_tracked(tmp_path)

    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "visible.txt").write_text("inside\n")
    (tmp_path / "tracked.txt").write_text("t2\n")

    result = await _extract_diff(project_dir=tmp_path)
    assert isinstance(result, DiffEntry)
    assert "tracked.txt" in result.diff_content
    assert ".hidden/visible.txt" in result.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_non_hidden_file_in_hidden_dir_should_not_show_when_ignored(
    tmp_path: Path,
):
    _init_repo_with_tracked(tmp_path)

    (tmp_path / ".gitignore").write_text(
        "**/.*\n!.gitignore\n!.gitattributes\n!.gitmodules\n"
    )
    subprocess.run(["git", "add", ".gitignore"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "add ignore"], cwd=tmp_path, check=True)

    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "visible.txt").write_text("inside\n")
    (tmp_path / "tracked.txt").write_text("t2\n")

    result = await _extract_diff(project_dir=tmp_path)
    assert isinstance(result, DiffEntry)
    assert "tracked.txt" in result.diff_content
    assert ".hidden/visible.txt" not in result.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_hidden_file_in_hidden_dir_should_show_when_not_ignored_and_extract_diff_wants_secret_files(
    tmp_path: Path,
):
    _init_repo_with_tracked(tmp_path)

    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / ".verysecret").write_text("shh\n")
    (tmp_path / "tracked.txt").write_text("t2\n")

    result = await _extract_diff(
        project_dir=tmp_path, exclude_hidden_folders_and_files_from_diff=False
    )
    assert isinstance(result, DiffEntry)
    assert "tracked.txt" in result.diff_content
    assert ".hidden/.verysecret" in result.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_hidden_file_in_hidden_dir_should_not_show_when_default_extract_diffs_ignores_hidden(
    tmp_path: Path,
):
    _init_repo_with_tracked(tmp_path)

    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / ".verysecret").write_text("shh\n")
    (tmp_path / "tracked.txt").write_text("t2\n")

    result = await _extract_diff(project_dir=tmp_path)
    assert isinstance(result, DiffEntry)
    assert "tracked.txt" in result.diff_content
    assert ".hidden/.verysecret" not in result.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_hidden_file_in_hidden_dir_should_not_show_when_ignored_and_extract_diff_does_not_want_secret_files(
    tmp_path: Path,
):
    _init_repo_with_tracked(tmp_path)

    (tmp_path / ".gitignore").write_text(
        "**/.*\n!.gitignore\n!.gitattributes\n!.gitmodules\n"
    )
    subprocess.run(["git", "add", ".gitignore"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "add ignore"], cwd=tmp_path, check=True)

    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / ".verysecret").write_text("shh\n")
    (tmp_path / "tracked.txt").write_text("t2\n")

    result = await _extract_diff(
        project_dir=tmp_path, exclude_hidden_folders_and_files_from_diff=False
    )
    assert isinstance(result, DiffEntry)
    assert "tracked.txt" in result.diff_content
    assert ".hidden/.verysecret" not in result.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_hidden_file_in_hidden_dir_should_not_show_when_ignored_and_extract_diff_wants_secret_files(
    tmp_path: Path,
):
    _init_repo_with_tracked(tmp_path)

    (tmp_path / ".gitignore").write_text(
        "**/.*\n!.gitignore\n!.gitattributes\n!.gitmodules\n"
    )
    subprocess.run(["git", "add", ".gitignore"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "add ignore"], cwd=tmp_path, check=True)

    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / ".verysecret").write_text("shh\n")
    (tmp_path / "tracked.txt").write_text("t2\n")

    result = await _extract_diff(
        project_dir=tmp_path, exclude_hidden_folders_and_files_from_diff=True
    )
    assert isinstance(result, DiffEntry)
    assert "tracked.txt" in result.diff_content
    assert ".hidden/.verysecret" not in result.diff_content


### ======================================
###    Test for extract_diff
###     With Mock-Task-State
### ======================================


class _StubRunCtx:
    def __init__(self, deps: TaskState):
        self.deps = deps


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_success_should_return_id_and_store_grows(tmp_path: Path):
    _setup_git_repo_with_change(tmp_path)
    state = TaskState(
        task=TestTask(root=".", issue_statement="Fix bug in foo.py"),
        git_repo=GitRepository(local_path=tmp_path),
    )
    ctx = _StubRunCtx(state)

    result = await extract_diff(ctx, project_dir=tmp_path)

    assert not isinstance(result, ToolErrorInfo)
    assert result.startswith("diff_")
    # store grew and contains the id
    assert len(state.diff_store) == 1
    assert result in state.diff_store.id_to_diff
    # diff_to_id reflects the addition
    assert len(state.diff_store.diff_to_id) == 1


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_when_no_changes_should_return_error_and_store_stays_empty(
    tmp_path: Path,
):
    _setup_git_repo_with_change(tmp_path)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "Apply change"], cwd=tmp_path, check=True)

    state = TaskState(
        task=TestTask(root=".", issue_statement="Fix bug in foo.py"),
        git_repo=GitRepository(local_path=tmp_path),
    )
    ctx = _StubRunCtx(state)

    result = await extract_diff(ctx, project_dir=tmp_path)

    assert isinstance(result, ToolErrorInfo)
    assert len(state.diff_store) == 0
    assert hasattr(result, "message")


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_duplicate_should_return_error_and_not_duplicate_in_store(
    tmp_path: Path,
):
    _setup_git_repo_with_change(tmp_path)
    state = TaskState(
        task=TestTask(root=".", issue_statement="Fix bug in foo.py"),
        git_repo=GitRepository(local_path=tmp_path),
    )
    ctx = _StubRunCtx(state)

    first = await extract_diff(ctx, project_dir=tmp_path)
    assert not isinstance(first, ToolErrorInfo)
    assert len(state.diff_store) == 1

    # Call again without making new changes: should detect duplicate
    second = await extract_diff(ctx, project_dir=tmp_path)

    assert not isinstance(second, str)  # should be an error object
    assert len(state.diff_store) == 1  # no new entry added


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_store_is_updated_proxies_reflect_change(tmp_path: Path):
    _setup_git_repo_with_change(tmp_path)
    state = TaskState(
        task=TestTask(root=".", issue_statement="Fix bug in foo.py"),
        git_repo=GitRepository(local_path=tmp_path),
    )
    ctx = _StubRunCtx(state)

    id_proxy = state.diff_store.id_to_diff  # live view
    assert len(id_proxy) == 0

    diff_id = await extract_diff(ctx, project_dir=tmp_path)
    assert not isinstance(diff_id, ToolErrorInfo)

    assert len(id_proxy) == 1
    assert diff_id in id_proxy

    dto = state.diff_store.diff_to_id
    assert len(dto) == 1

    stored_entry = state.diff_store.id_to_diff[diff_id]
    assert dto[stored_entry.diff_content] == diff_id
