import pytest
from pydantic import ValidationError

from useagent.pydantic_models.artifacts.git import DiffEntry, _is_valid_patch


def _wrap_in_codeblocks(
    to_wrap: str,
    newline_after_first_quote: bool = False,
    newline_before_first_quote: bool = False,
    newline_after_closing_quote: bool = False,
    with_codeblock_diff_annotation: bool = False,
) -> str:
    """
    Only used for tests, and to wrap things nicely without multiplying strings.
    """
    wrapped: str = (
        ("\n" if newline_before_first_quote else "")
        + "```"
        + ("diff\n" if with_codeblock_diff_annotation else "")
        + (
            "\n"
            if newline_after_first_quote and not with_codeblock_diff_annotation
            else ""
        )
        + to_wrap
        + "\n```"
        + ("\n" if newline_after_closing_quote else "")
    )
    return wrapped


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
index 0000000..e69de29
--- /dev/null
+++ b/newfile.txt
@@
+Hello world
"""

README_WITH_CODE_BLOCK = """\
diff --git a/README.md b/README.md
new file mode 100644
index 0000000..e69de29
--- /dev/null
+++ b/README.md
@@
+# Example
+
+```python
+print("hello")
+```
"""

PYTHON_SINGLE_QUOTED = """\
diff --git a/script.py b/script.py
new file mode 100644
index 0000000..e69de29
--- /dev/null
+++ b/script.py
@@
+msg = 'This is a single quoted string'
+print(msg)
"""

PYTHON_TRIPLE_QUOTED = """\
diff --git a/script.py b/script.py
new file mode 100644
index 0000000..e69de29
--- /dev/null
+++ b/script.py
@@
+msg = \"\"\"This is
+a triple quoted
+string.\"\"\"
+print(msg)
"""

FILE_REMOVAL = """\
diff --git a/oldfile.txt b/oldfile.txt
deleted file mode 100644
index e69de29..0000000
--- a/oldfile.txt
+++ /dev/null
@@
-Hello world
"""

ONE_LINE_CHANGE = """\
diff --git a/config.txt b/config.txt
index 3b18e93..5b6bcea 100644
--- a/config.txt
+++ b/config.txt
@@
-version=1.0
+version=1.1
"""

NO_INDEX_ADDITION = """\
diff --git a/foo.txt b/foo.txt
--- /dev/null
+++ b/foo.txt
@@
+Hello world
"""

NO_INDEX_MODIFICATION = """\
diff --git a/foo.txt b/foo.txt
--- a/foo.txt
+++ b/foo.txt
@@
-Hello
+Hello world
"""

MODE_CHANGE_ONLY = """\
diff --git a/foo.sh b/foo.sh
old mode 100644
new mode 100755
"""

RENAME_ONLY = """\
diff --git a/old_name.py b/new_name.py
similarity index 100%
rename from old_name.py
rename to new_name.py
"""

RENAME_AND_MODE_CHANGE = """\
diff --git a/old_name.sh b/new_name.sh
old mode 100644
new mode 100755
similarity index 100%
rename from old_name.sh
rename to new_name.sh
"""

TWO_HUNK_DIFF = """\
diff --git a/example.py b/example.py
index abc1234..def5678 100644
--- a/example.py
+++ b/example.py
@@ -1,3 +1,4 @@
+import os
 def foo():
     pass

@@ -10,7 +11,7 @@
 def bar():
-    return 42
+    return 43
"""

THREE_HUNK_DIFF = """\
diff --git a/sample.txt b/sample.txt
index 123abcd..456efgh 100644
--- a/sample.txt
+++ b/sample.txt
@@ -1,2 +1,3 @@
 Line 1
+Line 1.5

@@ -5,3 +6,3 @@
-Old line
+New line

@@ -10,0 +11,2 @@
+Appended line 1
+Appended line 2
"""


INVALID_NO_DIFF_HEADER = """\
--- a/file.txt
+++ b/file.txt
@@
-Hello
+Hi
"""

INVALID_ONLY_TEXT = """\
This is not a diff at all.
Just some random text.
"""

INVALID_ONLY_HEADER = """\
diff --git a/foo.txt b/foo.txt
"""

INVALID_MISSING_CHANGES = """\
diff --git a/foo.txt b/foo.txt
index 1234567..89abcde 100644
--- a/foo.txt
+++ b/foo.txt
"""


### ================================================================
###                              Basics
### ================================================================


@pytest.mark.pydantic_model
@pytest.mark.parametrize("notes", [None, "note", " explanation ", "\tinfo\n"])
def test_valid_diff_entry(notes: str | None):
    diff_content = EXAMPLE_GIT_DIFF
    DiffEntry(diff_content=diff_content, notes=notes)


@pytest.mark.pydantic_model
def test_diff_entry_with_starting_newline():
    EXAMPLE_GIT_DIFF_WITH_STARTING_NEWLINE: str = "\n" + EXAMPLE_GIT_DIFF
    DiffEntry(diff_content=EXAMPLE_GIT_DIFF_WITH_STARTING_NEWLINE)


@pytest.mark.pydantic_model
def test_diff_entry_with_ending_newline():
    EXAMPLE_GIT_DIFF_WITH_ENDING_NEWLINE: str = EXAMPLE_GIT_DIFF + "\n"
    DiffEntry(diff_content=EXAMPLE_GIT_DIFF_WITH_ENDING_NEWLINE)


@pytest.mark.pydantic_model
def test_diff_entry_wrapped_in_codeblocks():
    EXAMPLE_GIT_DIFF_IN_CODEBLOCKS = _wrap_in_codeblocks(EXAMPLE_GIT_DIFF)
    DiffEntry(diff_content=EXAMPLE_GIT_DIFF_IN_CODEBLOCKS)


@pytest.mark.pydantic_model
def test_diff_entry_wrapped_in_codeblocks_with_newlines():
    EXAMPLE_GIT_DIFF_IN_CODEBLOCKS_WITH_NEWLINE = _wrap_in_codeblocks(
        EXAMPLE_GIT_DIFF, newline_after_first_quote=True
    )
    DiffEntry(diff_content=EXAMPLE_GIT_DIFF_IN_CODEBLOCKS_WITH_NEWLINE)


@pytest.mark.pydantic_model
@pytest.mark.parametrize("diff_content", ["", " ", "\n", "\t"])
def test_whitespace_invalid_diff_content(diff_content: str):
    with pytest.raises(ValidationError):
        DiffEntry(diff_content=diff_content)


@pytest.mark.pydantic_model
@pytest.mark.parametrize("notes", ["", " ", "\n", "\t"])
def test_invalid_notes(notes: str):
    with pytest.raises(ValidationError):
        DiffEntry(diff_content="+ change", notes=notes)


@pytest.mark.parametrize(
    "patch",
    [
        NEW_FILE_ONE_LINE,
        MODE_CHANGE_ONLY,
        NO_INDEX_MODIFICATION,
    ],
)
def test_valid_patches(patch: str) -> None:
    assert _is_valid_patch(patch) is True


@pytest.mark.parametrize(
    "patch",
    [
        INVALID_ONLY_TEXT,
        INVALID_ONLY_HEADER,
        INVALID_MISSING_CHANGES,
        INVALID_NO_DIFF_HEADER,
    ],
)
def test_invalid_patches(patch: str) -> None:
    with pytest.raises(ValueError):
        _is_valid_patch(patch)


def test_code_block_wrapped_invalid_patch() -> None:
    wrapped = _wrap_in_codeblocks(INVALID_MISSING_CHANGES)
    with pytest.raises(ValueError):
        _is_valid_patch(wrapped)


def test_rename_only_patch() -> None:
    assert _is_valid_patch(RENAME_ONLY) is True


def test_rename_and_mode_change_patch() -> None:
    assert _is_valid_patch(RENAME_AND_MODE_CHANGE) is True


### ================================================================
###                            Computed Fields
### ================================================================


@pytest.mark.pydantic_model
@pytest.mark.parametrize(
    "diff_content,expected_index_flag",
    [
        (EXAMPLE_GIT_DIFF, True),
        (NO_INDEX_ADDITION, False),
        (NO_INDEX_MODIFICATION, False),
        (MODE_CHANGE_ONLY, False),
    ],
)
def test_has_index(diff_content: str, expected_index_flag: bool):
    entry = DiffEntry(diff_content=diff_content)
    assert entry.has_index == expected_index_flag


@pytest.mark.pydantic_model
@pytest.mark.parametrize(
    "diff_content,expected_hunks",
    [
        (EXAMPLE_GIT_DIFF, 1),
        (NEW_FILE_ONE_LINE, 1),
        (FILE_REMOVAL, 1),
        (ONE_LINE_CHANGE, 1),
        (MODE_CHANGE_ONLY, 0),
        (NO_INDEX_ADDITION, 1),
        (TWO_HUNK_DIFF, 2),
        (THREE_HUNK_DIFF, 3),
    ],
)
def test_number_of_hunks(diff_content: str, expected_hunks: int):
    entry = DiffEntry(diff_content=diff_content)
    assert entry.number_of_hunks == expected_hunks


@pytest.mark.pydantic_model
def test_code_block_flag_exact_wrap() -> None:
    content = _wrap_in_codeblocks(EXAMPLE_GIT_DIFF)
    entry = DiffEntry(diff_content=content)
    assert entry.is_wrapped_in_code_blocks


@pytest.mark.pydantic_model
def test_code_block_flag_newline_after_first_quote() -> None:
    content = _wrap_in_codeblocks(EXAMPLE_GIT_DIFF, newline_after_first_quote=True)
    entry = DiffEntry(diff_content=content)
    assert entry.is_wrapped_in_code_blocks


@pytest.mark.pydantic_model
def test_code_block_flag_newline_before_first_quote() -> None:
    content = _wrap_in_codeblocks(EXAMPLE_GIT_DIFF, newline_before_first_quote=True)
    entry = DiffEntry(diff_content=content)
    assert entry.is_wrapped_in_code_blocks


@pytest.mark.pydantic_model
def test_code_block_flag_newline_after_closing_quote() -> None:
    content = _wrap_in_codeblocks(EXAMPLE_GIT_DIFF, newline_after_closing_quote=True)
    entry = DiffEntry(diff_content=content)
    assert entry.is_wrapped_in_code_blocks


@pytest.mark.pydantic_model
def test_code_block_flag_unwrapped_input() -> None:
    entry = DiffEntry(diff_content=EXAMPLE_GIT_DIFF)
    assert not entry.is_wrapped_in_code_blocks


@pytest.mark.pydantic_model
def test_code_block_flag_diff_annotation_exact() -> None:
    content = _wrap_in_codeblocks(EXAMPLE_GIT_DIFF, with_codeblock_diff_annotation=True)
    entry = DiffEntry(diff_content=content)
    assert entry.is_wrapped_in_code_blocks


@pytest.mark.pydantic_model
def test_code_block_flag_diff_annotation_with_leading_newline() -> None:
    content = _wrap_in_codeblocks(
        EXAMPLE_GIT_DIFF,
        with_codeblock_diff_annotation=True,
        newline_before_first_quote=True,
    )
    entry = DiffEntry(diff_content=content)
    assert entry.is_wrapped_in_code_blocks


@pytest.mark.pydantic_model
def test_code_block_flag_diff_annotation_with_trailing_newline() -> None:
    content = _wrap_in_codeblocks(
        EXAMPLE_GIT_DIFF,
        with_codeblock_diff_annotation=True,
        newline_after_closing_quote=True,
    )
    entry = DiffEntry(diff_content=content)
    assert entry.is_wrapped_in_code_blocks


@pytest.mark.pydantic_model
@pytest.mark.parametrize(
    "diff_content,expected_flag",
    [
        (EXAMPLE_GIT_DIFF, True),
        (NEW_FILE_ONE_LINE, False),
        (FILE_REMOVAL, False),
    ],
)
def test_has_no_newline_eof_marker(diff_content: str, expected_flag: bool):
    entry = DiffEntry(diff_content=diff_content)
    assert entry.has_no_newline_eof_marker == expected_flag


### ================================================================
###                Errors and Others
### ================================================================


@pytest.mark.parametrize(
    "wrapped",
    [
        _wrap_in_codeblocks(EXAMPLE_GIT_DIFF),
        _wrap_in_codeblocks(EXAMPLE_GIT_DIFF, newline_after_closing_quote=True),
        _wrap_in_codeblocks(EXAMPLE_GIT_DIFF, newline_before_first_quote=True),
        _wrap_in_codeblocks(EXAMPLE_GIT_DIFF, with_codeblock_diff_annotation=True),
    ],
)
def test_wrapped_diff_is_valid(wrapped: str):
    entry = DiffEntry(diff_content=wrapped)
    assert entry.number_of_hunks > 0


@pytest.mark.pydantic_model
def test_get_output_instructions_should_not_return_none():
    assert DiffEntry.get_output_instructions()
