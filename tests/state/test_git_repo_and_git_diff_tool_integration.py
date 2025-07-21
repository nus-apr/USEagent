from pathlib import Path

import pytest

from useagent.state.git_repo import GitRepository
from useagent.tools.base import ToolResult
from useagent.tools.edit import extract_diff


@pytest.mark.asyncio
async def test_diff_after_repo_init_and_modification(tmp_path: Path):
    (tmp_path / "initial.txt").write_text("initial\n")
    GitRepository(str(tmp_path))

    (tmp_path / "initial.txt").write_text("changed\n")
    result = await extract_diff(project_dir=tmp_path)

    assert isinstance(result, ToolResult)
    assert "diff --git" in result.output
    assert "changed" in result.output


@pytest.mark.asyncio
async def test_diff_after_repo_clean(tmp_path: Path):
    (tmp_path / "file.txt").write_text("line\n")
    repo = GitRepository(str(tmp_path))

    (tmp_path / "file.txt").write_text("line modified\n")
    repo.repo_clean_changes()
    result = await extract_diff(project_dir=tmp_path)

    assert isinstance(result, ToolResult)
    assert result.output.strip() == "No changes detected in the repository."


@pytest.mark.asyncio
async def test_diff_after_file_addition(tmp_path: Path):
    GitRepository(str(tmp_path))

    (tmp_path / "new.txt").write_text("content\n")
    result = await extract_diff(project_dir=tmp_path)

    assert "diff --git" in result.output
    assert "new.txt" in result.output


@pytest.mark.asyncio
async def test_diff_ignores_gitignored_file(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("ignored.txt\n")
    (tmp_path / "tracked.txt").write_text("t\n")

    GitRepository(str(tmp_path))

    (tmp_path / "ignored.txt").write_text("ignore me\n")
    (tmp_path / "tracked.txt").write_text("t2\n")

    result = await extract_diff(project_dir=tmp_path)
    assert "ignored.txt" not in result.output
    assert "tracked.txt" in result.output


@pytest.mark.asyncio
async def test_diff_after_file_deletion(tmp_path: Path):
    f = tmp_path / "delete_me.txt"
    f.write_text("bye\n")
    GitRepository(str(tmp_path))

    f.unlink()
    result = await extract_diff(project_dir=tmp_path)
    assert "deleted file mode" in result.output
