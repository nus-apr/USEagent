import pytest

from useagent.pydantic_models.artifacts.git import DiffEntry, DiffStore
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo
from useagent.tools.meta import _remove_diffs_from_diff_store

EXAMPLE_GIT_DIFF_NEW_FILE_ONE_LINE = """\
diff --git a/newfile.txt b/newfile.txt
new file mode 100644
index 0000000..e69de29
--- /dev/null
+++ b/newfile.txt
@@
+Hello world
"""


EXAMPLE_GIT_DIFF_NEW_FILE_ONE_LINE_VARIATION = """\
diff --git a/newfile.txt b/newfile.txt
new file mode 100644
index 0000000..e69de29
--- /dev/null
+++ b/newfile.txt
@@
+Goodbye world
"""


@pytest.mark.tool
def test_remove_single_existing_key():
    store = DiffStore()
    k1 = store.add_entry(DiffEntry(diff_content=EXAMPLE_GIT_DIFF_NEW_FILE_ONE_LINE))
    store.add_entry(
        DiffEntry(diff_content=EXAMPLE_GIT_DIFF_NEW_FILE_ONE_LINE_VARIATION)
    )
    result = _remove_diffs_from_diff_store(store, [k1])
    assert isinstance(result, DiffStore)
    assert len(result) == 1
    # Note: This will reset the ids, so it will still have a diff_0
    # But the original_diff_0 content will still be there as the new diff_0
    data: str = store.id_to_diff["diff_0"].diff_content.strip()
    assert data == EXAMPLE_GIT_DIFF_NEW_FILE_ONE_LINE.strip()


@pytest.mark.tool
def test_remove_all_keys_results_empty_store():
    store = DiffStore()
    k1 = store.add_entry(DiffEntry(diff_content=EXAMPLE_GIT_DIFF_NEW_FILE_ONE_LINE))
    k2 = store.add_entry(
        DiffEntry(diff_content=EXAMPLE_GIT_DIFF_NEW_FILE_ONE_LINE_VARIATION)
    )
    result = _remove_diffs_from_diff_store(store, [k1, k2])
    assert isinstance(result, DiffStore)
    assert len(result) == 0


@pytest.mark.tool
def test_empty_key_list_returns_error():
    store = DiffStore()
    result = _remove_diffs_from_diff_store(store, [])
    assert isinstance(result, ToolErrorInfo)
    assert "no keys" in result.message.lower()


@pytest.mark.tool
def test_invalid_key_format_returns_error():
    store = DiffStore()
    store.add_entry(DiffEntry(diff_content=EXAMPLE_GIT_DIFF_NEW_FILE_ONE_LINE))
    result = _remove_diffs_from_diff_store(store, ["not_a_diff_key"])
    assert isinstance(result, ToolErrorInfo)
    assert "does not match the required format" in result.message


@pytest.mark.tool
def test_nonexistent_key_returns_error():
    store = DiffStore()
    store.add_entry(DiffEntry(diff_content=EXAMPLE_GIT_DIFF_NEW_FILE_ONE_LINE))
    result = _remove_diffs_from_diff_store(store, ["diff_999"])
    assert isinstance(result, ToolErrorInfo)
    assert "not in the existing DiffStore" in result.message


@pytest.mark.tool
def test_remove_selected_diffs_and_check_new_keys_are_reindexed():
    store = DiffStore()
    k0 = store.add_entry(
        DiffEntry(diff_content=EXAMPLE_GIT_DIFF_NEW_FILE_ONE_LINE + "\n1")
    )
    store.add_entry(DiffEntry(diff_content=EXAMPLE_GIT_DIFF_NEW_FILE_ONE_LINE + "\n2"))
    k2 = store.add_entry(
        DiffEntry(diff_content=EXAMPLE_GIT_DIFF_NEW_FILE_ONE_LINE + "\n3")
    )
    store.add_entry(DiffEntry(diff_content=EXAMPLE_GIT_DIFF_NEW_FILE_ONE_LINE + "\n4"))

    result = _remove_diffs_from_diff_store(store, [k0, k2])
    assert isinstance(result, DiffStore)
    assert len(result) == 2
    assert sorted(result.id_to_diff.keys()) == ["diff_0", "diff_1"]
