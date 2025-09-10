# DevNote:
# We have seen that the edit code often struggles to produce a new git diff when it chews on file changes.
# To combat this, we introduced a replace_file tool, which helps to avoid this a little bit.
# Or, at least we have seen that the agent would often like to fully replace the file.
# This integration test-suite is meant to show that the replace can lead to a successful diff extraction as expected.

from pathlib import Path

import pytest

from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo
from useagent.state.git_repo import GitRepository
from useagent.tools.edit import extract_diff, init_edit_tools, replace_file


@pytest.mark.integration
@pytest.mark.tool
@pytest.mark.asyncio
async def test_replace_file_then_extract_diff_should_show_modification(tmp_path: Path):
    init_edit_tools(str(tmp_path))

    target = tmp_path / "tracked.txt"
    target.write_text("v1\n")

    GitRepository(str(tmp_path))

    result_replace = replace_file("v2\n", str(target))
    assert isinstance(result_replace, CLIResult)
    assert target.read_text() == "v2\n"

    diff_result = await extract_diff(project_dir=tmp_path)
    assert isinstance(diff_result, CLIResult)
    assert "diff --git" in diff_result.output
    assert "tracked.txt" in diff_result.output
    assert "v2" in diff_result.output


@pytest.mark.integration
@pytest.mark.tool
@pytest.mark.asyncio
async def test_replace_file_failure_should_yield_toolerror_and_no_diff(tmp_path: Path):
    init_edit_tools(str(tmp_path))

    target = tmp_path / "tracked_bad.txt"
    target.write_text("original\n")

    GitRepository(str(tmp_path))

    bad_str = "abc\udcffdef"
    result_replace = replace_file(bad_str, target)
    assert isinstance(result_replace, ToolErrorInfo)

    diff_result = await extract_diff(project_dir=tmp_path)
    assert isinstance(diff_result, CLIResult)
    assert diff_result.output.strip() == "No changes detected in the repository."
