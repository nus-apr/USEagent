from pathlib import Path

import pytest

from useagent.pydantic_models.artifacts.git.diff import DiffEntry
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo
from useagent.state.git_repo import GitRepository
from useagent.tools.edit import init_edit_tools
from useagent.tools.git import _extract_diff


@pytest.mark.asyncio
async def test_diff_after_repo_init_and_modification(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    (tmp_path / "initial.txt").write_text("initial\n")
    GitRepository(str(tmp_path))

    (tmp_path / "initial.txt").write_text("changed\n")
    result = await _extract_diff(project_dir=tmp_path)

    assert isinstance(result, DiffEntry)
    assert "diff --git" in result.diff_content
    assert "changed" in result.diff_content


@pytest.mark.asyncio
async def test_diff_after_repo_clean_fails_due_to_no_changes(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    (tmp_path / "file.txt").write_text("line\n")
    repo = GitRepository(str(tmp_path))

    (tmp_path / "file.txt").write_text("line modified\n")
    repo.repo_clean_changes()
    result = await _extract_diff(project_dir=tmp_path)

    assert isinstance(result, ToolErrorInfo)


@pytest.mark.asyncio
async def test_diff_after_file_addition(tmp_path: Path):
    # DevNote after #44 we must have an existing commit and HEAD.
    init_edit_tools(str(tmp_path))
    GitRepository(str(tmp_path))

    (tmp_path / "new.txt").write_text("content\n")
    result = await _extract_diff(project_dir=tmp_path)

    assert isinstance(result, ToolErrorInfo)


@pytest.mark.asyncio
async def test_diff_ignores_gitignored_file(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    (tmp_path / ".gitignore").write_text("ignored.txt\n")
    (tmp_path / "tracked.txt").write_text("t\n")

    GitRepository(str(tmp_path))

    (tmp_path / "ignored.txt").write_text("ignore me\n")
    (tmp_path / "tracked.txt").write_text("t2\n")

    result = await _extract_diff(project_dir=tmp_path)
    assert "ignored.txt" not in result.diff_content
    assert "tracked.txt" in result.diff_content


@pytest.mark.asyncio
async def test_diff_after_file_deletion(tmp_path: Path):
    init_edit_tools(str(tmp_path))
    f = tmp_path / "delete_me.txt"
    f.write_text("bye\n")
    GitRepository(str(tmp_path))

    f.unlink()
    result = await _extract_diff(project_dir=tmp_path)
    assert "deleted file mode" in result.diff_content
