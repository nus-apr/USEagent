import pytest
from pydantic import ValidationError

from useagent.pydantic_models.artifacts.git import DiffEntry, DiffStore
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo
from useagent.tools.meta import _select_diff_from_diff_store

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
def test_empty_store_returns_error():
    store = DiffStore()
    result = _select_diff_from_diff_store(store, "diff_0")

    assert isinstance(result, ToolErrorInfo)
    assert "no diffs stored" in result.message.lower()


@pytest.mark.tool
def test_missing_key_returns_error():
    store = DiffStore()
    store.add_entry(DiffEntry(diff_content=EXAMPLE_GIT_DIFF_NEW_FILE_ONE_LINE))
    result = _select_diff_from_diff_store(store, "diff_1")

    assert isinstance(result, ToolErrorInfo)
    assert "diff_1" in result.message
    assert "diff_0" in result.message


@pytest.mark.tool
def test_single_entry_selection():
    store = DiffStore()
    key = store.add_entry(DiffEntry(diff_content=EXAMPLE_GIT_DIFF_NEW_FILE_ONE_LINE))
    result = _select_diff_from_diff_store(store, key)
    assert result.strip() == EXAMPLE_GIT_DIFF_NEW_FILE_ONE_LINE.strip()


@pytest.mark.regression
@pytest.mark.tool
def test_single_entry_selection_not_string_equal_due_to_stripping_whitespace():
    store = DiffStore()
    key = store.add_entry(DiffEntry(diff_content=EXAMPLE_GIT_DIFF_NEW_FILE_ONE_LINE))
    result = _select_diff_from_diff_store(store, key)
    assert not result == EXAMPLE_GIT_DIFF_NEW_FILE_ONE_LINE


@pytest.mark.tool
def test_two_entries_selection():
    store = DiffStore()
    k1 = store.add_entry(DiffEntry(diff_content=EXAMPLE_GIT_DIFF_NEW_FILE_ONE_LINE))
    k2 = store.add_entry(
        DiffEntry(diff_content=EXAMPLE_GIT_DIFF_NEW_FILE_ONE_LINE_VARIATION)
    )
    assert (
        _select_diff_from_diff_store(store, k1).strip()
        == EXAMPLE_GIT_DIFF_NEW_FILE_ONE_LINE.strip()
    )
    assert (
        _select_diff_from_diff_store(store, k2).strip()
        == EXAMPLE_GIT_DIFF_NEW_FILE_ONE_LINE_VARIATION.strip()
    )


@pytest.mark.pydantic_model
@pytest.mark.tool
def test_empty_diff_content_we_can_never_have_empty_diff_entries():
    with pytest.raises(ValidationError):
        # DevNote: We introduced constrained strings (constrs) to disallow any empty DiffEntry.
        store = DiffStore()
        key = store.add_entry(DiffEntry(diff_content=""))
        _select_diff_from_diff_store(store, key)
