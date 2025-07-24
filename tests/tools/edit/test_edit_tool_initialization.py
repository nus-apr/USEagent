from pathlib import Path

import pytest

import useagent.tools.edit as edit
from useagent.tools.edit import init_edit_tools


@pytest.mark.tool
def test_initialization_with_relative_dir_no_error():
    init_edit_tools(".")
    assert edit._project_dir == Path(".")


@pytest.mark.tool
def test_initialization_with_absolute_tempdir_no_error(tmp_path):
    init_edit_tools(tmp_path)
    assert edit._project_dir == Path(tmp_path)


@pytest.mark.tool
def test_initialization_with_none_gives_error():
    with pytest.raises(ValueError):
        init_edit_tools(None)


@pytest.mark.tool
def test_initialization_with_empty_string_gives_error():
    with pytest.raises(ValueError):
        init_edit_tools("")


@pytest.mark.tool
def test_initialization_with_whitespace_string_gives_error():
    with pytest.raises(ValueError):
        init_edit_tools("   ")


"""
DevNote: See Issue 10, there are some side effects still going on that make this test pass sometimes. 
@pytest.mark.asyncio
@pytest.mark.regression
@pytest.mark.tool
async def test_using_tool_without_initialization_throws_assertion_error(tmp_path):
    file = tmp_path / "new_file.txt"
    content = "This is a new file."
    with pytest.raises(AssertionError):
        await create(str(file), content)
"""
