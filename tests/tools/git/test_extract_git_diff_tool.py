import os
import stat
import subprocess
from pathlib import Path

import pytest

from useagent.config import ConfigSingleton
from useagent.pydantic_models.artifacts.git.diff import DiffEntry
from useagent.pydantic_models.task_state import TaskState
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo
from useagent.state.git_repo import GitRepository
from useagent.tasks.test_task import TestTask
from useagent.tools.git import _extract_diff, extract_diff

# DevNote:
# These tests will require that Git is installed and working.
# But given that you are using a git repository right now, that should be fine.


@pytest.fixture(autouse=True)
def reset_config():
    ConfigSingleton.reset()
    yield
    ConfigSingleton.reset()


@pytest.fixture(autouse=True)
def _reset_extract_counter():
    import useagent.tools.git as g

    g._EXTRACT_GIT_COUNTER = 0
    yield
    g._EXTRACT_GIT_COUNTER = 0


@pytest.fixture
def repo_cwd(tmp_path: Path):
    """cd into tmp repo for commands that rely on CWD (our extract runs in CWD)."""
    old = os.getcwd()
    os.chdir(tmp_path)
    try:
        yield tmp_path
    finally:
        os.chdir(old)


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


# -----------------------------
# _extract_diff (low-level)
# -----------------------------


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_real_changes(tmp_path: Path, repo_cwd):
    _setup_git_repo_with_change(tmp_path)

    result = await _extract_diff(paths_to_extract=".")

    assert isinstance(result, DiffEntry)
    assert "diff --git" in result.diff_content
    assert "+new line" in result.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_no_changes_after_commit(tmp_path: Path, repo_cwd):
    _setup_git_repo_with_change(tmp_path)
    os.system(f"cd {tmp_path} && git add . && git commit -m 'Apply change'")

    result = await _extract_diff(paths_to_extract=".")

    assert not isinstance(result, DiffEntry)


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_single_file_edit(tmp_path: Path, repo_cwd):
    _setup_git_repo_with_change(tmp_path)

    file = tmp_path / "test.txt"
    file.write_text("modified content\nanother line\n")

    result = await _extract_diff(paths_to_extract=".")

    assert "diff --git" in result.diff_content
    assert "+another line" in result.diff_content
    assert (
        "-original content" in result.diff_content
        or "+modified content" in result.diff_content
    )


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_respects_gitignore(tmp_path: Path, repo_cwd):
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

    (tmp_path / "ignored.txt").write_text("ignore me\n")
    (tmp_path / "tracked.txt").write_text("t2\n")

    result = await _extract_diff(paths_to_extract=".")
    assert "ignored.txt" not in result.diff_content
    assert "tracked.txt" in result.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_multiple_files(tmp_path: Path, repo_cwd):
    _setup_git_repo_with_change(tmp_path)

    other = tmp_path / "other.txt"
    other.write_text("initial\n")
    subprocess.run(["git", "add", "other.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "Add other file"], cwd=tmp_path, check=True)

    (tmp_path / "test.txt").write_text("changed\n")
    other.write_text("changed too\n")

    result = await _extract_diff(paths_to_extract=".")

    assert "diff --git a/test.txt" in result.diff_content
    assert "diff --git a/other.txt" in result.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_file_deletion(tmp_path: Path, repo_cwd):
    file = _setup_git_repo_with_change(tmp_path)

    file.unlink()

    result = await _extract_diff(paths_to_extract=".")

    assert "diff --git" in result.diff_content
    assert "deleted file mode" in result.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_nested_file(tmp_path: Path, repo_cwd):
    _setup_git_repo_with_change(tmp_path)

    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    nested_file = nested_dir / "nested.txt"
    nested_file.write_text("inside\n")

    subprocess.run(["git", "add", "nested/nested.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "Add nested file"], cwd=tmp_path, check=True)

    nested_file.write_text("modified\n")

    result = await _extract_diff(paths_to_extract=".")

    assert "diff --git a/nested/nested.txt" in result.diff_content
    assert "+modified" in result.diff_content


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_untracked_file_is_not_included(tmp_path: Path, repo_cwd):
    (tmp_path / "tracked.txt").write_text("initial\n")

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True
    )
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)

    (tmp_path / "untracked.txt").write_text("should not appear\n")

    result = await _extract_diff(paths_to_extract=".")
    assert isinstance(result, DiffEntry)
    assert "untracked.txt" in result.diff_content
    assert not result.diff_content.strip() == "No changes detected in the repository."


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_tracked_file_change_included_untracked_ignored(
    tmp_path: Path, repo_cwd
):
    (tmp_path / "a.txt").write_text("a\n")

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True
    )
    subprocess.run(["git", "add", "a.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)

    (tmp_path / "a.txt").write_text("a changed\n")
    (tmp_path / "new.txt").write_text("untracked\n")

    result = await _extract_diff(paths_to_extract=".")
    assert "diff --git a/a.txt" in result.diff_content
    assert "new.txt" in result.diff_content


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_issue_26__extract_diff_handles_non_utf8_text_file_change_should_not_crash(
    tmp_path: Path, repo_cwd
):
    _init_git_repo_without_content(tmp_path)
    p = tmp_path / "latin1.txt"
    p.write_bytes(b"hola\xa0mundo\n")
    subprocess.run(["git", "add", p.name], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "add latin1"], cwd=tmp_path, check=True)

    p.write_bytes(b"hola\xa0mundo\ncambio\xa0\n")

    result = await _extract_diff(paths_to_extract=".")
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
    tmp_path: Path, repo_cwd
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

        await _extract_diff(paths_to_extract=".")


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_issue_26__extract_diff_respects_non_utf8_filename_should_not_crash(
    tmp_path: Path, repo_cwd
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

    result = await _extract_diff(paths_to_extract=".")
    assert isinstance(result, DiffEntry)
    assert "diff --git" in result.diff_content
    assert fname in result.diff_content


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_issue_26__extract_diff_large_hunks_should_not_crash(
    tmp_path: Path, repo_cwd
):
    _init_git_repo_without_content(tmp_path)

    big = tmp_path / "big.txt"
    big.write_bytes(b"x" * (2 * 1024 * 1024))
    subprocess.run(["git", "add", big.name], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "add big"], cwd=tmp_path, check=True)

    big.write_bytes(big.read_bytes() + (b"\xa0" * (256 * 1024)) + b"\nmore\n")

    result = await _extract_diff(paths_to_extract=".")
    assert isinstance(result, DiffEntry)
    assert result.diff_content.strip()
    assert big.name in result.diff_content


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_issue_26__extract_diff_large_hunks_from_text_should_not_crash_and_not_be_truncated(
    tmp_path: Path, repo_cwd
):
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

    result = await _extract_diff(paths_to_extract=".")
    assert isinstance(result, ToolErrorInfo)


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_issue_41__extract_diff_missing_directory_should_return_tool_error_info(
    tmp_path: Path, repo_cwd
):
    missing = tmp_path / "does_not_exist"
    assert not missing.exists()
    result = await _extract_diff(paths_to_extract=str(missing))
    assert result
    assert isinstance(result, ToolErrorInfo)


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_issue_41__extract_diff_missing_file_should_return_tool_error_info(
    tmp_path: Path, repo_cwd
):
    missing = tmp_path / "does_not_exist.txt"
    assert not missing.exists()
    result = await _extract_diff(paths_to_extract=str(missing))
    assert result
    assert isinstance(result, ToolErrorInfo)


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_repo_without_commits_should_list_untracked(
    tmp_path: Path, repo_cwd
):
    # DevNote: This got deprecated with Issue #44 because we change the git extraction logic a bit.
    # Now we must have a git commit that was already initialized.
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True
    )

    (tmp_path / "new.txt").write_text("hello\n")

    result = await _extract_diff(paths_to_extract=".")
    assert not isinstance(result, DiffEntry)


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_rename_should_show_similarity_index(
    tmp_path: Path, repo_cwd
):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True
    )

    a = tmp_path / "a.txt"
    a.write_text("line1\nline2\nline3\n")
    subprocess.run(["git", "add", "a.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "add a"], cwd=tmp_path, check=True)

    subprocess.run(["git", "mv", "a.txt", "b.txt"], cwd=tmp_path, check=True)
    b = tmp_path / "b.txt"
    b.write_text("line1\nline2\nline3\nextra\n")

    result = await _extract_diff(paths_to_extract=".")
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
async def test__extract_diff_exec_bit_change_should_show_mode_change(
    tmp_path: Path, repo_cwd
):
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

    result = await _extract_diff(paths_to_extract=".")
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
async def test__extract_diff_symlink_target_change_should_be_reported(
    tmp_path: Path, repo_cwd
):
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
    os.symlink(tgt1.name, link)
    subprocess.run(
        ["git", "add", "target1.txt", "target2.txt", "link.txt"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(["git", "commit", "-m", "add link"], cwd=tmp_path, check=True)

    link.unlink()
    os.symlink(tgt2.name, link)

    result = await _extract_diff(paths_to_extract=".")
    assert "link.txt" in result.diff_content
    assert "120000" in result.diff_content or "symbolic link" in result.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_whitespace_only_change_behavior_should_show_change(
    tmp_path: Path, repo_cwd
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

    p.write_text("a   b   c\n")

    result = await _extract_diff(paths_to_extract=".")
    assert isinstance(result, DiffEntry)
    assert "diff --git" in result.diff_content
    assert "ws.txt" in result.diff_content


@pytest.mark.xfail(
    reason="Behavior changed - all hidden files are currently always excluded."
)
@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_hidden_file_in_root_should_show_when_not_ignored(
    tmp_path: Path, repo_cwd
):
    _init_repo_with_tracked(tmp_path)

    (tmp_path / ".hidden.txt").write_text("secret\n")
    (tmp_path / "tracked.txt").write_text("t2\n")

    result = await _extract_diff(
        exclude_hidden_folders_and_files_from_diff=False, paths_to_extract="."
    )
    assert isinstance(result, DiffEntry)
    assert "tracked.txt" in result.diff_content
    assert ".hidden.txt" in result.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_hidden_file_in_root_should_not_show_when_ignored(
    tmp_path: Path, repo_cwd
):
    _init_repo_with_tracked(tmp_path)

    (tmp_path / ".gitignore").write_text(
        "**/.*\n!.gitignore\n!.gitattributes\n!.gitmodules\n"
    )
    subprocess.run(["git", "add", ".gitignore"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "add ignore"], cwd=tmp_path, check=True)

    (tmp_path / ".hidden.txt").write_text("secret\n")
    (tmp_path / "tracked.txt").write_text("t2\n")

    result = await _extract_diff(paths_to_extract=".")
    assert isinstance(result, DiffEntry)
    assert "tracked.txt" in result.diff_content
    assert ".hidden.txt" not in result.diff_content


@pytest.mark.xfail(
    reason="Behavior changed - all hidden files are currently always excluded."
)
@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_non_hidden_file_in_hidden_dir_should_show_when_not_ignored(
    tmp_path: Path, repo_cwd
):
    _init_repo_with_tracked(tmp_path)

    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "visible.txt").write_text("inside\n")
    (tmp_path / "tracked.txt").write_text("t2\n")

    result = await _extract_diff(paths_to_extract=".")
    assert isinstance(result, DiffEntry)
    assert "tracked.txt" in result.diff_content
    assert ".hidden/visible.txt" in result.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_non_hidden_file_in_hidden_dir_should_not_show_when_ignored(
    tmp_path: Path, repo_cwd
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

    result = await _extract_diff(paths_to_extract=".")
    assert isinstance(result, DiffEntry)
    assert "tracked.txt" in result.diff_content
    assert ".hidden/visible.txt" not in result.diff_content


@pytest.mark.xfail(
    reason="Behavior changed - all hidden files are currently always excluded."
)
@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_hidden_file_in_hidden_dir_should_show_when_not_ignored_and_extract_diff_wants_secret_files(
    tmp_path: Path, repo_cwd
):
    _init_repo_with_tracked(tmp_path)

    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / ".verysecret").write_text("shh\n")
    (tmp_path / "tracked.txt").write_text("t2\n")

    result = await _extract_diff(
        exclude_hidden_folders_and_files_from_diff=False, paths_to_extract="."
    )
    assert isinstance(result, DiffEntry)
    assert "tracked.txt" in result.diff_content
    assert ".hidden/.verysecret" in result.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_hidden_file_in_hidden_dir_should_not_show_when_default_extract_diffs_ignores_hidden(
    tmp_path: Path, repo_cwd
):
    _init_repo_with_tracked(tmp_path)

    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / ".verysecret").write_text("shh\n")
    (tmp_path / "tracked.txt").write_text("t2\n")

    result = await _extract_diff(paths_to_extract=".")
    assert isinstance(result, DiffEntry)
    assert "tracked.txt" in result.diff_content
    assert ".hidden/.verysecret" not in result.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_hidden_file_in_hidden_dir_should_not_show_when_ignored_and_extract_diff_does_not_want_secret_files(
    tmp_path: Path, repo_cwd
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
        exclude_hidden_folders_and_files_from_diff=False, paths_to_extract="."
    )
    assert isinstance(result, DiffEntry)
    assert "tracked.txt" in result.diff_content
    assert ".hidden/.verysecret" not in result.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_hidden_file_in_hidden_dir_should_not_show_when_ignored_and_extract_diff_wants_secret_files(
    tmp_path: Path, repo_cwd
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
        exclude_hidden_folders_and_files_from_diff=True, paths_to_extract="."
    )
    assert isinstance(result, DiffEntry)
    assert "tracked.txt" in result.diff_content
    assert ".hidden/.verysecret" not in result.diff_content


# -----------------------------
# extract_diff (high-level)
# -----------------------------


class _StubRunCtx:
    def __init__(self, deps: TaskState):
        self.deps = deps


def _mk_ctx(tmp_path: Path) -> "_StubRunCtx":
    state = TaskState(
        task=TestTask(root=".", issue_statement="x"),
        git_repo=GitRepository(local_path=tmp_path),
    )
    return _StubRunCtx(state)


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_success_should_return_id_and_store_grows(
    tmp_path: Path, repo_cwd
):
    _setup_git_repo_with_change(tmp_path)
    state = TaskState(
        task=TestTask(root=".", issue_statement="Fix bug in foo.py"),
        git_repo=GitRepository(local_path=tmp_path),
    )
    ctx = _StubRunCtx(state)

    result = await extract_diff(ctx, paths_to_extract=".")

    assert not isinstance(result, ToolErrorInfo)
    assert result.startswith("diff_")
    assert len(state.diff_store) == 1
    assert result in state.diff_store.id_to_diff
    assert len(state.diff_store.diff_to_id) == 1


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_when_no_changes_should_return_error_and_store_stays_empty(
    tmp_path: Path, repo_cwd
):
    _setup_git_repo_with_change(tmp_path)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "Apply change"], cwd=tmp_path, check=True)

    state = TaskState(
        task=TestTask(root=".", issue_statement="Fix bug in foo.py"),
        git_repo=GitRepository(local_path=tmp_path),
    )
    ctx = _StubRunCtx(state)

    result = await extract_diff(ctx, paths_to_extract=".")

    assert isinstance(result, ToolErrorInfo)
    assert len(state.diff_store) == 0
    assert hasattr(result, "message")


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_duplicate_should_return_error_and_not_duplicate_in_store(
    tmp_path: Path, repo_cwd
):
    _setup_git_repo_with_change(tmp_path)
    state = TaskState(
        task=TestTask(root=".", issue_statement="Fix bug in foo.py"),
        git_repo=GitRepository(local_path=tmp_path),
    )
    ctx = _StubRunCtx(state)

    first = await extract_diff(ctx, paths_to_extract=".")
    assert not isinstance(first, ToolErrorInfo)
    assert len(state.diff_store) == 1

    second = await extract_diff(ctx, paths_to_extract=".")

    assert not isinstance(second, str)
    assert len(state.diff_store) == 1


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_store_is_updated_proxies_reflect_change(
    tmp_path: Path, repo_cwd
):
    _setup_git_repo_with_change(tmp_path)
    state = TaskState(
        task=TestTask(root=".", issue_statement="Fix bug in foo.py"),
        git_repo=GitRepository(local_path=tmp_path),
    )
    ctx = _StubRunCtx(state)

    id_proxy = state.diff_store.id_to_diff
    assert len(id_proxy) == 0

    diff_id = await extract_diff(ctx, paths_to_extract=".")
    assert not isinstance(diff_id, ToolErrorInfo)

    assert len(id_proxy) == 1
    assert diff_id in id_proxy

    dto = state.diff_store.diff_to_id
    assert len(dto) == 1

    stored_entry = state.diff_store.id_to_diff[diff_id]
    assert dto[stored_entry.diff_content] == diff_id


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_threshold_should_return_stuck_error_at_third_call(
    tmp_path: Path, repo_cwd
):
    _init_repo_with_tracked(tmp_path)
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["block-repeated-git-extracts"] = True
    ctx = _mk_ctx(tmp_path)

    (tmp_path / "tracked.txt").write_text("t2\n")
    ok = await extract_diff(ctx, paths_to_extract=".")
    assert isinstance(ok, str) and ok.startswith("diff_")

    r1 = await extract_diff(ctx, paths_to_extract=".")
    r2 = await extract_diff(ctx, paths_to_extract=".")
    await extract_diff(ctx, paths_to_extract=".")

    assert isinstance(r1, ToolErrorInfo)
    assert "stuck" not in r1.message.lower()
    assert isinstance(r2, ToolErrorInfo)
    assert "stuck" in r2.message.lower()


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_threshold_persists_should_keep_stuck_on_next_call(
    tmp_path: Path, repo_cwd
):
    _init_repo_with_tracked(tmp_path)
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["block-repeated-git-extracts"] = True
    ctx = _mk_ctx(tmp_path)

    (tmp_path / "tracked.txt").write_text("t2\n")
    ok = await extract_diff(ctx, paths_to_extract=".")
    assert isinstance(ok, str)

    (tmp_path / "tracked.txt").write_text("t3\n")

    await extract_diff(ctx, paths_to_extract=".")
    await extract_diff(ctx, paths_to_extract=".")
    await extract_diff(ctx, paths_to_extract=".")
    r4 = await extract_diff(ctx, paths_to_extract=".")

    assert isinstance(r4, ToolErrorInfo)
    assert "stuck" in r4.message.lower()


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_threshold_resets_on_edit_should_clear_stuck(
    tmp_path: Path, repo_cwd
):
    _init_repo_with_tracked(tmp_path)
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["block-repeated-git-extracts"] = True
    ctx = _mk_ctx(tmp_path)

    (tmp_path / "tracked.txt").write_text("t2\n")
    ok = await extract_diff(ctx, paths_to_extract=".")
    assert isinstance(ok, str)

    (tmp_path / "tracked.txt").write_text("t\n")
    await extract_diff(ctx, paths_to_extract=".")
    await extract_diff(ctx, paths_to_extract=".")
    await extract_diff(ctx, paths_to_extract=".")

    (tmp_path / "tracked.txt").write_text("t3\n")
    r = await extract_diff(ctx, paths_to_extract=".")
    assert isinstance(r, str) and r.startswith("diff_")
    assert isinstance(ctx.deps.diff_store.id_to_diff[r], DiffEntry)


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_after_reset_should_not_immediately_return_stuck(
    tmp_path: Path, repo_cwd
):
    _init_repo_with_tracked(tmp_path)
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["block-repeated-git-extracts"] = True
    ctx = _mk_ctx(tmp_path)

    (tmp_path / "tracked.txt").write_text("t2\n")
    ok = await extract_diff(ctx, paths_to_extract=".")
    assert isinstance(ok, str)

    (tmp_path / "tracked.txt").write_text("t\n")
    await extract_diff(ctx, paths_to_extract=".")
    await extract_diff(ctx, paths_to_extract=".")
    await extract_diff(ctx, paths_to_extract=".")

    (tmp_path / "tracked.txt").write_text("t3\n")
    ok2 = await extract_diff(ctx, paths_to_extract=".")
    assert isinstance(ok2, str)

    (tmp_path / "tracked.txt").write_text("t\n")
    r_next = await extract_diff(ctx, paths_to_extract=".")
    assert isinstance(r_next, ToolErrorInfo)
    assert "stuck" not in r_next.message.lower()


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_threshold_toggle_off_should_not_trigger_stuck(
    tmp_path: Path, repo_cwd
):
    _init_repo_with_tracked(tmp_path)
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["block-repeated-git-extracts"] = False
    ctx = _mk_ctx(tmp_path)

    (tmp_path / "tracked.txt").write_text("t2\n")
    ok = await extract_diff(ctx, paths_to_extract=".")
    assert isinstance(ok, str)

    (tmp_path / "tracked.txt").write_text("t\n")
    r1 = await extract_diff(ctx, paths_to_extract=".")
    r2 = await extract_diff(ctx, paths_to_extract=".")
    r3 = await extract_diff(ctx, paths_to_extract=".")
    r4 = await extract_diff(ctx, paths_to_extract=".")

    for r in (r1, r2, r3, r4):
        assert isinstance(r, ToolErrorInfo)
        assert "stuck" not in r.message.lower()


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_no_changes_four_times_should_never_trigger_stuck(
    tmp_path: Path, repo_cwd
):
    _init_repo_with_tracked(tmp_path)
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["block-repeated-git-extracts"] = True
    ctx = _mk_ctx(tmp_path)

    r1 = await extract_diff(ctx, paths_to_extract=".")
    r2 = await extract_diff(ctx, paths_to_extract=".")
    r3 = await extract_diff(ctx, paths_to_extract=".")
    r4 = await extract_diff(ctx, paths_to_extract=".")

    for r in (r1, r2, r3, r4):
        assert isinstance(r, ToolErrorInfo)
        assert "stuck" not in r.message.lower()


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_added_line_starting_with_pluses_should_extract(
    tmp_path: Path, repo_cwd
):
    _init_git_repo_without_content(tmp_path)

    p = tmp_path / "file.txt"
    p.write_text("line1\nold\nend\n", encoding="utf-8")
    subprocess.run(["git", "add", p.name], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)

    p.write_text("line1\nnew\n+++ not a header\nend\n", encoding="utf-8")

    result = await _extract_diff(paths_to_extract=".")

    assert isinstance(result, DiffEntry)
    dc = result.diff_content
    assert "diff --git a/file.txt b/file.txt" in dc
    assert "+++ not a header" in dc
    assert "@@ " in dc


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test__extract_diff_multihunk_with_added_plusplusplus_and_crlf_should_extract(
    tmp_path: Path, repo_cwd
):
    _init_git_repo_without_content(tmp_path)

    p = tmp_path / "multi.txt"
    block1 = "line1\r\nold\r\nend\r\n"
    gap = "".join(f"ctx{i}\r\n" for i in range(10))
    block2 = "keep\r\nfoo\r\n"
    p.write_bytes((block1 + gap + block2).encode("utf-8"))
    subprocess.run(["git", "add", p.name], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)

    block1_mod = "line1\r\nnew\r\n+++ not a header\r\nend\r\n"
    block2_mod = "keep\r\nbar\r\n"
    p.write_bytes((block1_mod + gap + block2_mod).encode("utf-8"))

    result = await _extract_diff(paths_to_extract=".")

    assert isinstance(result, DiffEntry)
    dc = result.diff_content
    assert "diff --git a/multi.txt b/multi.txt" in dc
    assert "+++ not a header" in dc
    assert dc.count("@@ ") >= 2


@pytest.mark.tool
@pytest.mark.asyncio
async def test_unstage_after_extract_should_leave_index_clean(tmp_path: Path, repo_cwd):
    # init repo with one tracked file
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    p = tmp_path / "a.txt"
    p.write_text("one\n")
    subprocess.run(["git", "add", "a.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)

    # modify file; _extract_diff will stage with --intent-to-add, then unstage in finally
    p.write_text("one\nchange\n")

    r = await _extract_diff(paths_to_extract="a.txt")
    assert isinstance(r, DiffEntry)

    # index must be clean (no staged changes)
    proc = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert proc.stdout.strip() == ""


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_two_files_in_two_folders_should_include_both(
    tmp_path: Path, repo_cwd
):
    # repo with two subfolders and one file each
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)

    (tmp_path / "dir1").mkdir()
    (tmp_path / "dir2").mkdir()
    f1 = tmp_path / "dir1" / "a.txt"
    f2 = tmp_path / "dir2" / "b.txt"
    f1.write_text("x\n")
    f2.write_text("y\n")
    subprocess.run(["git", "add", "dir1/a.txt", "dir2/b.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)

    # modify both
    f1.write_text("x\nc1\n")
    f2.write_text("y\nc2\n")

    r = await _extract_diff(paths_to_extract=[str(f1), str(f2)])
    assert isinstance(r, DiffEntry)
    dc = r.diff_content
    assert "diff --git a/dir1/a.txt b/dir1/a.txt" in dc
    assert "diff --git a/dir2/b.txt b/dir2/b.txt" in dc


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_two_files_should_not_include_third_neighbor(
    tmp_path: Path, repo_cwd
):
    # repo with three sibling files
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)

    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    c = tmp_path / "c.txt"
    for p in (a, b, c):
        p.write_text("v1\n")
    subprocess.run(["git", "add", "a.txt", "b.txt", "c.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)

    # modify all three
    a.write_text("v2\n")
    b.write_text("v2\n")
    c.write_text("v2\n")

    # only include a and b
    r = await _extract_diff(paths_to_extract=["a.txt", "b.txt"])
    assert isinstance(r, DiffEntry)
    dc = r.diff_content
    assert "diff --git a/a.txt b/a.txt" in dc
    assert "diff --git a/b.txt b/b.txt" in dc
    assert "diff --git a/c.txt b/c.txt" not in dc


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_by_pattern_txt_should_ignore_md(tmp_path: Path, repo_cwd):
    # repo with .txt and .md
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)

    t1 = tmp_path / "foo.txt"
    t2 = tmp_path / "bar.txt"
    m1 = tmp_path / "note.md"
    t1.write_text("A\n")
    t2.write_text("B\n")
    m1.write_text("M\n")
    subprocess.run(
        ["git", "add", "foo.txt", "bar.txt", "note.md"], cwd=tmp_path, check=True
    )
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)

    # modify all
    t1.write_text("A changed\n")
    t2.write_text("B changed\n")
    m1.write_text("M changed\n")

    # only include *.txt (pattern is passed through as-is)
    r = await _extract_diff(paths_to_extract="*.txt")
    assert isinstance(r, DiffEntry)
    dc = r.diff_content
    assert "diff --git a/foo.txt b/foo.txt" in dc
    assert "diff --git a/bar.txt b/bar.txt" in dc
    assert "diff --git a/note.md b/note.md" not in dc


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_nonexistent_folder_should_return_toolerror(
    tmp_path: Path, repo_cwd
):
    missing_dir = tmp_path / "does_not_exist_dir"
    assert not missing_dir.exists()

    result = await _extract_diff(paths_to_extract=str(missing_dir))
    assert isinstance(result, ToolErrorInfo)


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_nonexistent_file_should_return_toolerror(
    tmp_path: Path, repo_cwd
):
    missing_file = tmp_path / "missing.txt"
    assert not missing_file.exists()

    result = await _extract_diff(paths_to_extract=str(missing_file))
    assert isinstance(result, ToolErrorInfo)


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_invalid_pattern_should_return_toolerror(
    tmp_path: Path, repo_cwd
):
    # Invalid pathspec that git will reject
    bad_pattern = ":(bad-syntax"

    result = await _extract_diff(paths_to_extract=bad_pattern)
    assert isinstance(result, ToolErrorInfo)


@pytest.mark.regression
@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_preserves_working_tree_change_and_repeats_on_next_call(
    tmp_path: Path, repo_cwd
):
    # init repo and track file
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)

    p = tmp_path / "tracked.txt"
    p.write_text("v1\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)

    # modify working tree (tracked -> changed)
    p.write_text("v2\n")

    # 1) extract: file must be in diff entry
    r1 = await _extract_diff(paths_to_extract="tracked.txt")
    assert isinstance(r1, DiffEntry)
    assert "diff --git a/tracked.txt b/tracked.txt" in r1.diff_content
    assert "+v2" in r1.diff_content or "-v1" in r1.diff_content

    # 2) after extract: changes must remain in working tree, and NOT be staged
    cached = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    wt = subprocess.run(
        ["git", "diff", "--name-only"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert cached == ""  # not staged
    assert wt.splitlines() == ["tracked.txt"]  # still modified

    # 3) call again without changing anything: it should appear again
    r2 = await _extract_diff(paths_to_extract="tracked.txt")
    assert isinstance(r2, DiffEntry)
    assert "diff --git a/tracked.txt b/tracked.txt" in r2.diff_content
