# DevNote:
# We have seen that the edit code often struggles to produce a new git diff when it chews on file changes.
# To combat this, we introduced a replace_file tool, which helps to avoid this a little bit.
# Or, at least we have seen that the agent would often like to fully replace the file.
# This integration test-suite is meant to show that the replace can lead to a successful diff extraction as expected.

from pathlib import Path

import pytest

from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo
from useagent.state.git_repo import GitRepository
from useagent.tools.edit import init_edit_tools, replace_file
from useagent.tools.git import _extract_diff


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

    result = await _extract_diff(paths_to_extract=tmp_path)
    assert isinstance(result, ToolErrorInfo)
