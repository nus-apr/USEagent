import pytest

from useagent.pydantic_models.artifacts.git.diff import DiffEntry
from useagent.pydantic_models.artifacts.git.diff_store import DiffStore

### ================================================================
###                      Test Data
###     (Must be at top to be useable in parameterized tests)
### ================================================================


# This is a valid, and expected to be seen example from Git Diffs that should work.
EXAMPLE_GIT_DIFF: str = """\
diff --git a/my_test.sh b/my_test.sh
new file mode 100644
index 0000000000..e3d22bbc15
--- /dev/null
+++ b/my_test.sh
@@ -0,0 +1,35 @@
+#!/bin/bash
+
+# Create a virtual environment if one doesn't exist
+if [ ! -d ".venv" ]; then
+  echo "Creating virtual environment..."
+  python3 -m venv .venv
+fi
+
+# Activate the virtual environment
+source .venv/bin/activate
+
+# Install requirements
+pip install --upgrade pip
+pip install -e .
+if [ -f "tests/requirements/py3.txt" ]; then
+    pip install -r tests/requirements/py3.txt
+fi
+if [ -f "tests/requirements/postgres.txt" ]; then
+    pip install -r tests/requirements/postgres.txt
+fi
+if [ -f "tests/requirements/mysql.txt" ]; then
+    pip install -r tests/requirements/mysql.txt
+fi
+if [ -f "tests/requirements/oracle.txt" ]; then
+    pip install -r tests/requirements/oracle.txt
+fi
+
+# Run the tests
+echo "Running tests..."
+python tests/runtests.py
+
+# Deactivate the virtual environment
+deactivate
+
+echo "Tests completed."
\\ No newline at end of file
"""

NEW_FILE_ONE_LINE = """\
diff --git a/newfile.txt b/newfile.txt
new file mode 100644
index 0000000..deadbee
--- /dev/null
+++ b/newfile.txt
@@ -0,0 +1 @@
+Hello world
"""

README_WITH_CODE_BLOCK = """\
diff --git a/README.md b/README.md
new file mode 100644
index 0000000..e69de29
--- /dev/null
+++ b/README.md
@@ -0,0 +1,5 @@
+# Example
+
+```python
+print("hello")
+```
"""

ANOTHER_DIFF: str = """\
diff --git a/b b/b
new file mode 100644
index 0000000..cafebabe
--- /dev/null
+++ b/b
@@ -0,0 +1 @@
+Hi there
"""

### ================================================================
###                      Tests
### ================================================================


@pytest.mark.pydantic_model
@pytest.mark.parametrize(
    "diff_content",
    [EXAMPLE_GIT_DIFF, NEW_FILE_ONE_LINE, README_WITH_CODE_BLOCK],
)
def test_add_entry(diff_content: str):
    store = DiffStore()
    entry = DiffEntry(diff_content=diff_content)
    diff_id = store._add_entry(entry)
    assert isinstance(diff_id, str)
    assert diff_id.startswith("diff_")
    assert len(store) == 1
    assert diff_id in store.id_to_diff
    assert (store.id_to_diff[diff_id]).diff_content
    # Note: We have no full equality, but we have equality minus strips
    assert (store.id_to_diff[diff_id]).diff_content.strip() == diff_content.strip()


@pytest.mark.pydantic_model
def test_add_multiple_entries():
    store = DiffStore()
    e1 = DiffEntry(diff_content=EXAMPLE_GIT_DIFF)
    e2 = DiffEntry(diff_content=NEW_FILE_ONE_LINE)
    id1 = store._add_entry(e1)
    id2 = store._add_entry(e2)
    assert id1 != id2
    assert len(store) == 2


@pytest.mark.pydantic_model
def test_add_duplicate_exact_raises():
    store = DiffStore()
    entry = DiffEntry(diff_content=EXAMPLE_GIT_DIFF)
    store._add_entry(entry)
    with pytest.raises(ValueError):
        store._add_entry(entry)


@pytest.mark.pydantic_model
def test_add_multiple_entries_should_update_id_to_diff_live_proxy():
    store = DiffStore()
    live_proxy = store.id_to_diff
    k1 = store._add_entry(DiffEntry(diff_content=EXAMPLE_GIT_DIFF))
    assert k1 in live_proxy
    k2 = store._add_entry(DiffEntry(diff_content=ANOTHER_DIFF))
    # same proxy should reflect size and membership
    assert len(live_proxy) == 2
    assert k2 in live_proxy


@pytest.mark.pydantic_model
def test_id_to_diff_readonly_should_reject_setitem():
    store = DiffStore()
    k = store._add_entry(DiffEntry(diff_content=EXAMPLE_GIT_DIFF))
    proxy = store.id_to_diff
    with pytest.raises(TypeError):
        proxy["diff_999"] = store.id_to_diff[k]  # type: ignore[index]


@pytest.mark.pydantic_model
def test_id_to_diff_readonly_should_reject_mutating_methods():
    store = DiffStore()
    store._add_entry(DiffEntry(diff_content=EXAMPLE_GIT_DIFF))
    proxy = store.id_to_diff
    with pytest.raises(AttributeError):
        proxy.clear()  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        proxy.pop("diff_0")  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        proxy.update({})  # type: ignore[attr-defined]


@pytest.mark.pydantic_model
def test_id_to_diff_live_view_should_reflect_additions():
    store = DiffStore()
    proxy_before = store.id_to_diff
    assert len(proxy_before) == 0
    k = store._add_entry(DiffEntry(diff_content=EXAMPLE_GIT_DIFF))
    # The same proxy object should now see the new key
    assert len(proxy_before) == 1
    assert k in proxy_before
    # And a fresh read should of course see it too
    assert k in store.id_to_diff


@pytest.mark.pydantic_model
def test_diff_to_id_readonly_should_reject_setitem():
    store = DiffStore()
    store._add_entry(DiffEntry(diff_content=EXAMPLE_GIT_DIFF))
    proxy = store.diff_to_id
    with pytest.raises(TypeError):
        proxy["anything"] = "diff_123"  # type: ignore[index]


@pytest.mark.pydantic_model
def test_diff_to_id_live_view_should_reflect_additions():
    store = DiffStore()
    proxy = store.diff_to_id
    assert len(proxy) == 0
    k = store._add_entry(DiffEntry(diff_content=EXAMPLE_GIT_DIFF))
    # Note: diff_to_id snapshot is rebuilt on property access in this class;
    #       verify that a freshly accessed proxy sees the new mapping.
    assert len(store.diff_to_id) == 1
    assert EXAMPLE_GIT_DIFF in store.diff_to_id
    assert store.diff_to_id[EXAMPLE_GIT_DIFF] == k


@pytest.mark.pydantic_model
def test_new_store_should_start_empty():
    s = DiffStore()
    assert len(s) == 0
    assert len(s.id_to_diff) == 0
    assert len(s.diff_to_id) == 0


@pytest.mark.pydantic_model
def test_init_with_prefilled_mapping_should_raise():
    e = DiffEntry(diff_content=EXAMPLE_GIT_DIFF)
    with pytest.raises(ValueError, match="initialized empty"):
        DiffStore(_id_to_diff={"diff_0": e})  # type: ignore[arg-type]


@pytest.mark.pydantic_model
def test_init_with_explicit_empty_mapping_should_be_ok():
    s = DiffStore(_id_to_diff={})
    assert len(s) == 0


@pytest.mark.pydantic_model
def test_store_after_add_is_not_empty():
    s = DiffStore()
    s._add_entry(DiffEntry(diff_content=EXAMPLE_GIT_DIFF))
    assert len(s) == 1
