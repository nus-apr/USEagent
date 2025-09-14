import os
import subprocess
from pathlib import Path

import pytest

from useagent.pydantic_models.artifacts.git.diff import DiffEntry
from useagent.pydantic_models.task_state import TaskState
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo
from useagent.state.git_repo import GitRepository
from useagent.tasks.test_task import TestTask
from useagent.tools.edit import _read_file_as_diff, init_edit_tools, read_file_as_diff


def _git(cmd: list[str], cwd: Path) -> None:
    subprocess.run(["git", *cmd], cwd=cwd, check=True, capture_output=True)


@pytest.mark.tool
@pytest.mark.asyncio
async def test_read_file_as_diff_should_error_when_file_missing(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    missing = tmp_path / "does_not_exist.txt"

    result = await _read_file_as_diff(missing)

    assert isinstance(result, ToolErrorInfo)
    assert "does not exist" in result.message.lower()


@pytest.mark.tool
@pytest.mark.asyncio
async def test_read_file_as_diff_should_error_when_path_is_dir(tmp_path: Path):
    init_edit_tools(str(tmp_path))

    result = await _read_file_as_diff(tmp_path)

    assert isinstance(result, ToolErrorInfo)
    assert "directory" in result.message.lower()


@pytest.mark.tool
@pytest.mark.asyncio
async def test_read_file_as_diff_should_return_patch_for_new_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    init_edit_tools(str(tmp_path))
    _git(["init"], tmp_path)
    # user.name/email not required for diff, but harmless if defaults are missing
    _git(["config", "user.name", "tester"], tmp_path)
    _git(["config", "user.email", "tester@example.com"], tmp_path)

    file = tmp_path / "hello.txt"
    file.write_text("line1\nline2\n")

    # ensure git runs in repo root
    monkeypatch.chdir(tmp_path)
    result = await _read_file_as_diff(file)

    assert isinstance(result, DiffEntry)
    out = result.diff_content
    assert "hello.txt" in out
    assert "diff --git" in out
    assert "+line1" in out
    assert "+line2" in out


@pytest.mark.tool
@pytest.mark.asyncio
async def test_read_file_as_diff_should_accept_path_and_str_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    init_edit_tools(str(tmp_path))
    _git(["init"], tmp_path)

    p = tmp_path / "dual.txt"
    p.write_text("a\nb\n")

    monkeypatch.chdir(tmp_path)
    res_path = await _read_file_as_diff(p)
    res_str = await _read_file_as_diff(str(p))

    assert isinstance(res_path, DiffEntry)
    assert isinstance(res_str, DiffEntry)
    assert "dual.txt" in res_path.diff_content
    assert "dual.txt" in res_str.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test_read_file_as_diff_should_change_when_appending_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "append.txt"
    file.write_text("line1\n")

    monkeypatch.chdir(tmp_path)
    first = await _read_file_as_diff(file)
    file.write_text("line1\nline2\n")
    second = await _read_file_as_diff(file)

    assert isinstance(first, DiffEntry)
    assert isinstance(second, DiffEntry)
    assert first.diff_content != second.diff_content
    assert "+line2" in second.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test_read_file_as_diff_should_completely_change_when_overwriting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "overwrite.txt"
    file.write_text("one\n")
    monkeypatch.chdir(tmp_path)
    first = await _read_file_as_diff(file)

    file.write_text("completely different\n")
    second = await _read_file_as_diff(file)

    assert isinstance(first, DiffEntry)
    assert isinstance(second, DiffEntry)
    assert first.diff_content != second.diff_content
    assert "completely different" in second.diff_content
    assert "one" not in second.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test_read_file_as_diff_should_handle_empty_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "empty.txt"
    file.write_text("")

    monkeypatch.chdir(tmp_path)
    result = await _read_file_as_diff(file)

    assert isinstance(result, DiffEntry)
    # still should mention the file but with no additions
    assert "empty.txt" in result.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test_read_file_as_diff_should_handle_whitespace_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "space.txt"
    file.write_text("   \n\t\n")

    monkeypatch.chdir(tmp_path)
    result = await _read_file_as_diff(file)

    assert isinstance(result, DiffEntry)
    assert "space.txt" in result.diff_content
    assert "+" in result.diff_content  # additions present


@pytest.mark.tool
@pytest.mark.asyncio
async def test_read_file_as_diff_should_work_with_relative_and_parent_segments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    init_edit_tools(str(tmp_path))
    sub = tmp_path / "sub"
    sub.mkdir()
    f = tmp_path / "file.txt"
    f.write_text("x\n")
    monkeypatch.chdir(sub)
    rel = Path("..") / "file.txt"
    res = await _read_file_as_diff(rel)
    assert isinstance(res, DiffEntry)
    assert "file.txt" in res.diff_content


@pytest.mark.tool
@pytest.mark.asyncio
async def test_read_file_as_diff_should_not_work_with_spaces_and_unicode_in_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    init_edit_tools(str(tmp_path))
    fname = tmp_path / "my file – ünicode.txt"
    fname.write_text("content\n")
    monkeypatch.chdir(tmp_path)
    res = await _read_file_as_diff(fname)
    assert isinstance(res, ToolErrorInfo)


@pytest.mark.tool
@pytest.mark.asyncio
@pytest.mark.skipif(os.name == "nt", reason="symlinks need admin on Windows")
async def test_read_file_as_diff_simlinks_are_printed_as_diffs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    init_edit_tools(str(tmp_path))
    target = tmp_path / "target.txt"
    target.write_text("data\n")
    link = tmp_path / "link.txt"
    link.symlink_to(target)
    monkeypatch.chdir(tmp_path)
    res = await _read_file_as_diff(link)
    assert isinstance(res, DiffEntry)


@pytest.mark.tool
@pytest.mark.asyncio
@pytest.mark.skipif(os.name == "nt", reason="symlinks need admin on Windows")
async def test_read_file_as_diff_should_error_on_broken_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    init_edit_tools(str(tmp_path))
    broken = tmp_path / "broken.txt"
    broken.symlink_to(tmp_path / "missing.txt")
    monkeypatch.chdir(tmp_path)
    res = await _read_file_as_diff(broken)
    assert isinstance(res, ToolErrorInfo)
    assert "does not exist" in res.message.lower()


@pytest.mark.tool
@pytest.mark.asyncio
@pytest.mark.skipif(os.name == "nt", reason="symlinks need admin on Windows")
async def test_read_file_as_diff_should_error_on_directory_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    init_edit_tools(str(tmp_path))
    d = tmp_path / "dir"
    d.mkdir()
    dlink = tmp_path / "dirlink"
    dlink.symlink_to(d, target_is_directory=True)
    monkeypatch.chdir(tmp_path)
    res = await _read_file_as_diff(dlink)
    assert isinstance(res, ToolErrorInfo)
    assert "directory" in res.message.lower()


class _StubRunCtx:
    def __init__(self, deps: TaskState):
        self.deps = deps


@pytest.mark.tool
@pytest.mark.asyncio
async def test_read_file_as_diff_success_should_return_id_and_store_grows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _git(["init"], tmp_path)
    _git(["config", "user.name", "tester"], tmp_path)
    _git(["config", "user.email", "tester@example.com"], tmp_path)

    f = tmp_path / "hello.txt"
    f.write_text("line1\nline2\n")
    monkeypatch.chdir(tmp_path)

    state = TaskState(
        task=TestTask(root=".", issue_statement="Read file"),
        git_repo=GitRepository(local_path=tmp_path),
    )
    ctx = _StubRunCtx(state)

    result = await read_file_as_diff(ctx, f)

    assert isinstance(result, str) and result.startswith("diff_")
    assert len(state.diff_store) == 1
    assert result in state.diff_store.id_to_diff


@pytest.mark.tool
@pytest.mark.asyncio
async def test_read_file_as_diff_missing_should_return_error_and_store_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _git(["init"], tmp_path)
    monkeypatch.chdir(tmp_path)

    missing = tmp_path / "does_not_exist.txt"
    state = TaskState(
        task=TestTask(root=".", issue_statement="Missing"),
        git_repo=GitRepository(local_path=tmp_path),
    )
    ctx = _StubRunCtx(state)

    res = await read_file_as_diff(ctx, missing)

    assert isinstance(res, ToolErrorInfo)
    assert len(state.diff_store) == 0


@pytest.mark.tool
@pytest.mark.asyncio
async def test_read_file_as_diff_dir_should_return_error_and_store_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _git(["init"], tmp_path)
    monkeypatch.chdir(tmp_path)

    state = TaskState(
        task=TestTask(root=".", issue_statement="Dir path"),
        git_repo=GitRepository(local_path=tmp_path),
    )
    ctx = _StubRunCtx(state)

    res = await read_file_as_diff(ctx, tmp_path)

    assert isinstance(res, ToolErrorInfo)
    assert len(state.diff_store) == 0


@pytest.mark.tool
@pytest.mark.asyncio
async def test_read_file_as_diff_duplicate_should_return_error_and_not_duplicate_in_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _git(["init"], tmp_path)
    _git(["config", "user.name", "tester"], tmp_path)
    _git(["config", "user.email", "tester@example.com"], tmp_path)

    p = tmp_path / "dup.txt"
    p.write_text("a\nb\n")
    monkeypatch.chdir(tmp_path)

    state = TaskState(
        task=TestTask(root=".", issue_statement="Dup"),
        git_repo=GitRepository(local_path=tmp_path),
    )
    ctx = _StubRunCtx(state)

    first = await read_file_as_diff(ctx, p)
    assert isinstance(first, str)
    assert len(state.diff_store) == 1

    second = await read_file_as_diff(ctx, p)
    assert isinstance(second, ToolErrorInfo)
    assert len(state.diff_store) == 1
    assert first in second.message  # function should mention existing ID


@pytest.mark.tool
@pytest.mark.asyncio
async def test_read_file_as_diff_relative_and_parent_segments_should_work_and_store_grows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _git(["init"], tmp_path)
    _git(["config", "user.name", "tester"], tmp_path)
    _git(["config", "user.email", "tester@example.com"], tmp_path)

    sub = tmp_path / "sub"
    sub.mkdir()
    f = tmp_path / "file.txt"
    f.write_text("x\n")

    state = TaskState(
        task=TestTask(root=".", issue_statement="Rel path"),
        git_repo=GitRepository(local_path=tmp_path),
    )
    ctx = _StubRunCtx(state)

    monkeypatch.chdir(sub)
    rel = Path("..") / "file.txt"
    rid = await read_file_as_diff(ctx, rel)

    assert isinstance(rid, str) and rid.startswith("diff_")
    assert len(state.diff_store) == 1
    assert rid in state.diff_store.id_to_diff


@pytest.mark.tool
@pytest.mark.asyncio
@pytest.mark.skipif(os.name == "nt", reason="symlinks need admin on Windows")
async def test_read_file_as_diff_symlink_should_return_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _git(["init"], tmp_path)
    target = tmp_path / "target.txt"
    target.write_text("data\n")
    link = tmp_path / "link.txt"
    link.symlink_to(target)

    state = TaskState(
        task=TestTask(root=".", issue_statement="Symlink"),
        git_repo=GitRepository(local_path=tmp_path),
    )
    ctx = _StubRunCtx(state)

    monkeypatch.chdir(tmp_path)
    rid = await read_file_as_diff(ctx, link)

    assert isinstance(rid, str) and rid.startswith("diff_")
    assert len(state.diff_store) == 1


@pytest.mark.tool
@pytest.mark.asyncio
@pytest.mark.skipif(os.name == "nt", reason="symlinks need admin on Windows")
async def test_read_file_as_diff_broken_symlink_should_error_and_store_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _git(["init"], tmp_path)
    broken = tmp_path / "broken.txt"
    broken.symlink_to(tmp_path / "missing.txt")

    state = TaskState(
        task=TestTask(root=".", issue_statement="Broken link"),
        git_repo=GitRepository(local_path=tmp_path),
    )
    ctx = _StubRunCtx(state)

    monkeypatch.chdir(tmp_path)
    res = await read_file_as_diff(ctx, broken)

    assert isinstance(res, ToolErrorInfo)
    assert len(state.diff_store) == 0
