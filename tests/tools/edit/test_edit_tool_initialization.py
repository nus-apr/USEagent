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
