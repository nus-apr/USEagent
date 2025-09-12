import pytest

from useagent.pydantic_models.artifacts.git import DiffEntry, DiffStore

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
@@ -0,0 +5 @@
+# Example
+
+```python
+print("hello")
+```
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
    diff_id = store.add_entry(entry)
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
    id1 = store.add_entry(e1)
    id2 = store.add_entry(e2)
    assert id1 != id2
    assert len(store) == 2


@pytest.mark.pydantic_model
def test_invalid_key_rejected():
    with pytest.raises(ValueError):
        DiffStore(
            id_to_diff={"": DiffEntry(diff_content=NEW_FILE_ONE_LINE)}
        )  # invalid NonEmptyStr


@pytest.mark.pydantic_model
def test_add_duplicate_exact_raises():
    store = DiffStore()
    entry = DiffEntry(diff_content=EXAMPLE_GIT_DIFF)
    store.add_entry(entry)
    with pytest.raises(ValueError):
        store.add_entry(entry)


@pytest.mark.pydantic_model
def test_diffstore_model_validator_rejects_duplicate_on_init():
    entry1 = DiffEntry(diff_content=NEW_FILE_ONE_LINE)
    entry2 = DiffEntry(diff_content=NEW_FILE_ONE_LINE)
    with pytest.raises(ValueError, match="Duplicate diff contents detected"):
        DiffStore(id_to_diff={"diff_0": entry1, "diff_1": entry2})


@pytest.mark.pydantic_model
def test_diffstore_model_validator_rejects_invalid_key_on_init():
    entry = DiffEntry(diff_content=EXAMPLE_GIT_DIFF)
    with pytest.raises(ValueError, match="Invalid key in DiffStore"):
        DiffStore(id_to_diff={"invalid_key": entry})


@pytest.mark.pydantic_model
def test_diff_to_id_property_maps_normalized_content():
    store = DiffStore()
    e1 = DiffEntry(diff_content=NEW_FILE_ONE_LINE + "\n")
    e2 = DiffEntry(diff_content=EXAMPLE_GIT_DIFF)
    k1 = store.add_entry(e1)
    k2 = store.add_entry(e2)
    result = store.diff_to_id
    assert result == {NEW_FILE_ONE_LINE.strip(): k1, EXAMPLE_GIT_DIFF.strip(): k2}
