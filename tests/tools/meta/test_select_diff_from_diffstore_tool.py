import pytest

from useagent.pydantic_models.git import DiffEntry, DiffStore
from useagent.tools.base import ToolError
from useagent.tools.meta import _select_diff_from_diff_store


@pytest.mark.tool
def test_empty_store_raises():
    store = DiffStore()
    with pytest.raises(ToolError, match="no diffs stored"):
        _select_diff_from_diff_store(store, "diff_0")


@pytest.mark.tool
def test_missing_key_raises():
    store = DiffStore()
    store.add_entry(DiffEntry(diff_content="diff a"))
    with pytest.raises(
        ToolError,
        match="Key diff_1 was not in the diff_store. Available keys in diff_store: diff_0",
    ):
        _select_diff_from_diff_store(store, "diff_1")


@pytest.mark.tool
def test_single_entry_selection():
    store = DiffStore()
    key = store.add_entry(DiffEntry(diff_content="diff a"))
    result = _select_diff_from_diff_store(store, key)
    assert result == "diff a"


@pytest.mark.tool
def test_two_entries_selection():
    store = DiffStore()
    k1 = store.add_entry(DiffEntry(diff_content="first"))
    k2 = store.add_entry(DiffEntry(diff_content="second"))
    assert _select_diff_from_diff_store(store, k1) == "first"
    assert _select_diff_from_diff_store(store, k2) == "second"


@pytest.mark.tool
def test_empty_diff_content():
    store = DiffStore()
    key = store.add_entry(DiffEntry(diff_content=""))
    result = _select_diff_from_diff_store(store, key)
    assert result == ""
