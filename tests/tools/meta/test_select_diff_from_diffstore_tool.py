import pytest

from useagent.pydantic_models.git import DiffEntry, DiffStore
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo
from useagent.tools.meta import _select_diff_from_diff_store


@pytest.mark.tool
def test_empty_store_returns_error():
    store = DiffStore()
    result = _select_diff_from_diff_store(store, "diff_0")

    assert isinstance(result, ToolErrorInfo)
    assert result.tool == "select_diff_from_diff_store"
    assert "no diffs stored" in result.message.lower()


@pytest.mark.tool
def test_missing_key_returns_error():
    store = DiffStore()
    store.add_entry(DiffEntry(diff_content="diff a"))
    result = _select_diff_from_diff_store(store, "diff_1")

    assert isinstance(result, ToolErrorInfo)
    assert result.tool == "select_diff_from_diff_store"
    assert "diff_1" in result.message
    assert "diff_0" in result.message


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
