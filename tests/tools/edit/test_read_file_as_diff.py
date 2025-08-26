import os
import subprocess
from pathlib import Path

import pytest

from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo
from useagent.tools.edit import init_edit_tools, read_file_as_diff


def _git(cmd: list[str], cwd: Path) -> None:
    subprocess.run(["git", *cmd], cwd=cwd, check=True, capture_output=True)


@pytest.mark.tool
@pytest.mark.asyncio
async def test_read_file_as_diff_should_error_when_file_missing(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    missing = tmp_path / "does_not_exist.txt"

    result = await read_file_as_diff(missing)

    assert isinstance(result, ToolErrorInfo)
    assert "does not exist" in result.message.lower()


@pytest.mark.tool
@pytest.mark.asyncio
async def test_read_file_as_diff_should_error_when_path_is_dir(tmp_path: Path):
    init_edit_tools(str(tmp_path))

    result = await read_file_as_diff(tmp_path)

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
    result = await read_file_as_diff(file)

    assert isinstance(result, CLIResult)
    out = result.output
    assert "patch" in out.lower()
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
    res_path = await read_file_as_diff(p)
    res_str = await read_file_as_diff(str(p))

    assert isinstance(res_path, CLIResult)
    assert isinstance(res_str, CLIResult)
    assert "dual.txt" in res_path.output
    assert "dual.txt" in res_str.output


@pytest.mark.tool
@pytest.mark.asyncio
async def test_read_file_as_diff_should_change_when_appending_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "append.txt"
    file.write_text("line1\n")

    monkeypatch.chdir(tmp_path)
    first = await read_file_as_diff(file)
    file.write_text("line1\nline2\n")
    second = await read_file_as_diff(file)

    assert isinstance(first, CLIResult)
    assert isinstance(second, CLIResult)
    assert first.output != second.output
    assert "+line2" in second.output


@pytest.mark.tool
@pytest.mark.asyncio
async def test_read_file_as_diff_should_completely_change_when_overwriting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "overwrite.txt"
    file.write_text("one\n")
    monkeypatch.chdir(tmp_path)
    first = await read_file_as_diff(file)

    file.write_text("completely different\n")
    second = await read_file_as_diff(file)

    assert isinstance(first, CLIResult)
    assert isinstance(second, CLIResult)
    assert first.output != second.output
    assert "completely different" in second.output
    assert "one" not in second.output


@pytest.mark.tool
@pytest.mark.asyncio
async def test_read_file_as_diff_should_handle_empty_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "empty.txt"
    file.write_text("")

    monkeypatch.chdir(tmp_path)
    result = await read_file_as_diff(file)

    assert isinstance(result, CLIResult)
    # still should mention the file but with no additions
    assert "empty.txt" in result.output


@pytest.mark.tool
@pytest.mark.asyncio
async def test_read_file_as_diff_should_handle_whitespace_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    init_edit_tools(str(tmp_path))
    file = tmp_path / "space.txt"
    file.write_text("   \n\t\n")

    monkeypatch.chdir(tmp_path)
    result = await read_file_as_diff(file)

    assert isinstance(result, CLIResult)
    assert "space.txt" in result.output
    assert "+" in result.output  # additions present


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
    res = await read_file_as_diff(rel)
    assert isinstance(res, CLIResult)
    assert "file.txt" in res.output


@pytest.mark.tool
@pytest.mark.asyncio
async def test_read_file_as_diff_should_not_work_with_spaces_and_unicode_in_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    init_edit_tools(str(tmp_path))
    fname = tmp_path / "my file – ünicode.txt"
    fname.write_text("content\n")
    monkeypatch.chdir(tmp_path)
    res = await read_file_as_diff(fname)
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
    res = await read_file_as_diff(link)
    assert isinstance(res, CLIResult)


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
    res = await read_file_as_diff(broken)
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
    res = await read_file_as_diff(dlink)
    assert isinstance(res, ToolErrorInfo)
    assert "directory" in res.message.lower()
