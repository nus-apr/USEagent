import subprocess
from pathlib import Path

import pytest

from useagent.pydantic_models.artifacts.git import DiffEntry
from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.tools.git import extract_diff


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_real_changes_should_build_diffentry(tmp_path: Path):
    # init + change
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True
    )
    p = tmp_path / "a.txt"
    p.write_text("x\n")
    subprocess.run(["git", "add", "a.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)
    p.write_text("x\ny\n")

    res = await extract_diff(project_dir=tmp_path)
    assert isinstance(res, CLIResult)
    assert "diff --git" in res.output and "@@" in res.output

    entry = DiffEntry(diff_content=res.output)
    assert entry.number_of_hunks >= 1


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_single_file_edit_should_build_diffentry(tmp_path: Path):
    # base repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True
    )
    p = tmp_path / "test.txt"
    p.write_text("original\n")
    subprocess.run(["git", "add", "test.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)

    # edit
    p.write_text("original\nanother\n")

    res = await extract_diff(project_dir=tmp_path)
    assert "diff --git" in res.output
    entry = DiffEntry(diff_content=res.output)
    assert entry.number_of_hunks >= 1


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_multiple_files_should_build_diffentry(tmp_path: Path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True
    )
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("a\n")
    b.write_text("b\n")
    subprocess.run(["git", "add", "a.txt", "b.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)

    a.write_text("a changed\n")
    b.write_text("b changed\n")

    res = await extract_diff(project_dir=tmp_path)
    assert "diff --git a/a.txt" in res.output and "diff --git a/b.txt" in res.output
    entry = DiffEntry(diff_content=res.output)
    assert entry.number_of_hunks >= 1


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_file_deletion_should_build_diffentry(tmp_path: Path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True
    )
    p = tmp_path / "gone.txt"
    p.write_text("bye\n")
    subprocess.run(["git", "add", "gone.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "add"], cwd=tmp_path, check=True)

    p.unlink()

    res = await extract_diff(project_dir=tmp_path)
    assert "diff --git" in res.output and "deleted file mode" in res.output
    entry = DiffEntry(diff_content=res.output)
    # header-only block is valid; hunks may be 0 for pure delete with no context shown
    assert isinstance(entry.number_of_hunks, int)


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_nested_file_should_build_diffentry(tmp_path: Path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True
    )

    d = tmp_path / "dir"
    d.mkdir()
    f = d / "n.txt"
    f.write_text("one\n")
    subprocess.run(["git", "add", "dir/n.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "add"], cwd=tmp_path, check=True)

    f.write_text("one\ntwo\n")
    res = await extract_diff(project_dir=tmp_path)
    assert "diff --git a/dir/n.txt" in res.output
    entry = DiffEntry(diff_content=res.output)
    assert entry.has_index in (True, False)  # just ensure it parses


@pytest.mark.tool
@pytest.mark.asyncio
async def test_extract_diff_unicode_filename_should_build_diffentry(tmp_path: Path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True
    )
    subprocess.run(
        ["git", "config", "core.quotepath", "false"], cwd=tmp_path, check=True
    )

    fname = "über 🧪.txt"
    p = tmp_path / fname
    p.write_text("hi\n")
    subprocess.run(["git", "add", fname], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "add"], cwd=tmp_path, check=True)

    p.write_text("hi\nchanged\n")
    res = await extract_diff(project_dir=tmp_path)
    assert "diff --git" in res.output and fname in res.output

    entry = DiffEntry(diff_content=res.output)
    assert entry.number_of_hunks >= 1
