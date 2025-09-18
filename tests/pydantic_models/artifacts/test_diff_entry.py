import pytest
from pydantic import ValidationError

from useagent.pydantic_models.artifacts.git.diff import DiffEntry, _is_valid_patch

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

PYTHON_SINGLE_QUOTED = """\
diff --git a/script.py b/script.py
new file mode 100644
index 0000000..e69de29
--- /dev/null
+++ b/script.py
@@ -0,0 +2 @@
+msg = 'This is a single quoted string'
+print(msg)
"""

PYTHON_TRIPLE_QUOTED = """\
diff --git a/script.py b/script.py
new file mode 100644
index 0000000..e69de29
--- /dev/null
+++ b/script.py
@@ -0,0 +4 @@
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
@@ -1 +0,0 @@
-Hello world
"""

ONE_LINE_CHANGE = """\
diff --git a/config.txt b/config.txt
index 3b18e93..5b6bcea 100644
--- a/config.txt
+++ b/config.txt
@@ -1 +1 @@
-version=1.0
+version=1.1
"""

NO_INDEX_ADDITION = """\
diff --git a/foo.txt b/foo.txt
--- /dev/null
+++ b/foo.txt
@@ -0,0 +1 @@
+Hello world
"""

NO_INDEX_MODIFICATION = """\
diff --git a/foo.txt b/foo.txt
--- a/foo.txt
+++ b/foo.txt
@@ -1 +1 @@
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
--- a/example.py
+++ b/example.py
@@ -1,2 +1,3 @@
+import os
 def foo():
     pass

@@ -5,2 +5,2 @@
 def bar():
-    return 42
+    return 43
"""

THREE_HUNK_DIFF = """\
diff --git a/sample.txt b/sample.txt
--- a/sample.txt
+++ b/sample.txt
@@ -1,1 +1,2 @@
 Line 1
+Line 1.5

@@ -5,1 +5,1 @@
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


FROM_CORRUPTED_PATCH_TESTS = """\
diff --git a/test.txt b/test.txt
index 2fd0152..4791a8d 100644
--- a/test.txt
+++ b/test.txt
@@ -1 +1,2 @@
 original content
+new line
"""

### ================================================================
###                              Basics
### ================================================================


@pytest.mark.pydantic_model
def test_diff_entry_with_starting_newline():
    EXAMPLE_GIT_DIFF_WITH_STARTING_NEWLINE: str = "\n" + EXAMPLE_GIT_DIFF
    DiffEntry(diff_content=EXAMPLE_GIT_DIFF_WITH_STARTING_NEWLINE)


@pytest.mark.pydantic_model
def test_diff_entry_with_ending_newline():
    EXAMPLE_GIT_DIFF_WITH_ENDING_NEWLINE: str = EXAMPLE_GIT_DIFF + "\n"
    DiffEntry(diff_content=EXAMPLE_GIT_DIFF_WITH_ENDING_NEWLINE)


@pytest.mark.pydantic_model
@pytest.mark.parametrize("diff_content", ["", " ", "\n", "\t"])
def test_whitespace_invalid_diff_content(diff_content: str):
    with pytest.raises(ValidationError):
        DiffEntry(diff_content=diff_content)


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


@pytest.mark.pydantic_model
@pytest.mark.regression
def test_issue_43_diffentry_string_cleaning_will_not_lead_to_corrupted_patch():
    entry = DiffEntry(diff_content=FROM_CORRUPTED_PATCH_TESTS)
    assert entry
    assert entry.diff_content.endswith("\n")


### ================================================================
###                Errors and Others
### ================================================================


@pytest.mark.pydantic_model
def test_get_output_instructions_should_not_return_none():
    assert DiffEntry.get_output_instructions()


# This was retrieved on 2025-09-11 for swebench, but its an invalid patch for two reasons:
#   The hunk does not specify lines (and close with @@)
#   And there is garbage at the end of the patch with the *** End Patch
# That one is just hallucinated I guess
SWE_MISSING_HUNK_EXAMPLE: str = """
diff --git a/xarray/core/variable.py b/xarray/core/variable.py
--- a/xarray/core/variable.py
+++ b/xarray/core/variable.py
@@
-    # we don't want nested self-described arrays
-    data = getattr(data, "values", data)
+    # we don't want nested self-described arrays
+    if hasattr(data, "values"):
+        mod = getattr(data.__class__, "__module__", "")
+        if isinstance(mod, str) and (mod.startswith("pandas") or mod.startswith("xarray")):
+            data = data.values
diff --git a/xarray/tests/test_variable.py b/xarray/tests/test_variable.py
--- a/xarray/tests/test_variable.py
+++ b/xarray/tests/test_variable.py
@@
-        assert v[0, 1] == 1
-
-    def test_setitem_fancy(self):
+        assert v[0, 1] == 1
+
+    def test_setitem_preserve_object_with_values_attr(self):
+        # ensure objects with a .values attribute that is not from pandas/xarray
+        # are preserved when assigned into object-dtype Variables
+        arr = np.empty((1,), dtype=object)
+        arr[0] = None
+        v = self.cls("x", arr)
+
+        class HasValues:
+            def __init__(self, val):
+                self.values = val
+
+        inst = HasValues(5)
+        v[0] = inst
+        # the assigned object should be preserved, not unwrapped
+        assert v.values[0] is inst
+        assert v.dtype == object
+
+    def test_setitem_fancy(self):
*** End Patch
"""


@pytest.mark.regression
def test_issue_44_patch_has_only_opening_hunks_does_not_make_valid_diff_entry():
    with pytest.raises(ValidationError):
        DiffEntry(diff_content=SWE_MISSING_HUNK_EXAMPLE)


SWE_ONE_MISSING_HUNK_ONE_EXISTING_HUNK: str = '''
diff --git a/astropy/units/quantity.py b/astropy/units/quantity.py
index b98abfafb..f3265634e 100644
--- a/astropy/units/quantity.py
+++ b/astropy/units/quantity.py
@@
-        # and the unit of the result (or tuple of units for nout > 1).
-        converters, unit = converters_and_unit(function, method, *inputs)
+        # and the unit of the result (or tuple of units for nout > 1).
+        try:
+            converters, unit = converters_and_unit(function, method, *inputs)
+        except (TypeError, ValueError, UnitConversionError, UnitsError, UnitTypeError):
+            # If we cannot determine converters/units for the given inputs,
+            # this operation is not implemented for Quantity; allow other
+            # array-like objects to handle it by returning NotImplemented.
+            return NotImplemented
@@
         out = kwargs.get("out", None)
         # Avoid loop back by turning any Quantity output into array views.
diff --git a/astropy/units/tests/test_array_ufunc_not_implemented.py b/astropy/units/tests/test_array_ufunc_not_implemented.py
new file mode 100644
index 000000000..3c5b13655
--- /dev/null
+++ b/astropy/units/tests/test_array_ufunc_not_implemented.py
@@ -0,0 +1,30 @@
+import numpy as np
+import astropy.units as u
+
+
+class DuckArray:
+    """A minimal duck array that implements __array_ufunc__ and returns a
+    sentinel to indicate it handled the operation.
+    """
+
+    def __init__(self, value):
+        self.value = np.asarray(value)
+
+    def __array_ufunc__(self, ufunc, method, *inputs, **kwargs):
+        # Return a DuckArray instance so tests can detect that our duck was
+        # used to implement the operation.
+        return DuckArray(0)
+
+
+def test_quantity_returns_notimplemented_for_incompatible_input():
+    q = 1 * u.m
+    res = q + DuckArray(1 * u.mm)
+    # If Quantity returns NotImplemented, the DuckArray.__array_ufunc__ should
+    # be called and thus the result should be a DuckArray instance.
+    assert isinstance(res, DuckArray)
+
+
+def test_duckarray_plus_quantity_works():
+    q = 1 * u.m
+    res = DuckArray(1 * u.mm) + q
+    assert isinstance(res, DuckArray)
'''


@pytest.mark.regression
def test_issue_44_patch_has_some_correct_some_incorrect_hunks_does_not_make_valid_diff_entry():
    with pytest.raises(ValidationError):
        DiffEntry(diff_content=SWE_ONE_MISSING_HUNK_ONE_EXISTING_HUNK)


SWE_VALID_DIFF_BUT_WITH_GARBAGE: str = """\
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
*** End Patch
"""


@pytest.mark.regression
def test_issue_44_patch_has_garbage_does_not_make_valid_diff_entry():
    with pytest.raises(ValidationError):
        DiffEntry(diff_content=SWE_VALID_DIFF_BUT_WITH_GARBAGE)


@pytest.mark.regression
def test_issue_44_patch_has_only_opening_hunks_does_not_make_valid_diff_entry_var2():
    with pytest.raises(ValidationError):
        DiffEntry(diff_content=SWE_MISSING_HUNK_EXAMPLE)


SWE_CORRECT_PART_OF_LARGER_PATCH: str = '''
diff --git a/astropy/units/tests/test_array_ufunc_not_implemented.py b/astropy/units/tests/test_array_ufunc_not_implemented.py
new file mode 100644
index 000000000..3c5b13655
--- /dev/null
+++ b/astropy/units/tests/test_array_ufunc_not_implemented.py
@@ -0,0 +1,30 @@
+import numpy as np
+import astropy.units as u
+
+
+class DuckArray:
+    """A minimal duck array that implements __array_ufunc__ and returns a
+    sentinel to indicate it handled the operation.
+    """
+
+    def __init__(self, value):
+        self.value = np.asarray(value)
+
+    def __array_ufunc__(self, ufunc, method, *inputs, **kwargs):
+        # Return a DuckArray instance so tests can detect that our duck was
+        # used to implement the operation.
+        return DuckArray(0)
+
+
+def test_quantity_returns_notimplemented_for_incompatible_input():
+    q = 1 * u.m
+    res = q + DuckArray(1 * u.mm)
+    # If Quantity returns NotImplemented, the DuckArray.__array_ufunc__ should
+    # be called and thus the result should be a DuckArray instance.
+    assert isinstance(res, DuckArray)
+
+
+def test_duckarray_plus_quantity_works():
+    q = 1 * u.m
+    res = DuckArray(1 * u.mm) + q
+    assert isinstance(res, DuckArray)
'''


@pytest.mark.regression
def test_issue_44_patch_only_correct_part_of_patch_should_still_work():
    # Just the 2nd part of the patch should be valid, just to check that my changes don't invalidate something else.
    assert DiffEntry(diff_content=SWE_CORRECT_PART_OF_LARGER_PATCH)


SWE_FAILING_PART_OF_LARGER_PATCH: str = """
diff --git a/astropy/units/quantity.py b/astropy/units/quantity.py
index b98abfafb..f3265634e 100644
--- a/astropy/units/quantity.py
+++ b/astropy/units/quantity.py
@@
-        # and the unit of the result (or tuple of units for nout > 1).
-        converters, unit = converters_and_unit(function, method, *inputs)
+        # and the unit of the result (or tuple of units for nout > 1).
+        try:
+            converters, unit = converters_and_unit(function, method, *inputs)
+        except (TypeError, ValueError, UnitConversionError, UnitsError, UnitTypeError):
+            # If we cannot determine converters/units for the given inputs,
+            # this operation is not implemented for Quantity; allow other
+            # array-like objects to handle it by returning NotImplemented.
+            return NotImplemented
@@
         out = kwargs.get("out", None)
         # Avoid loop back by turning any Quantity output into array views.
"""


@pytest.mark.regression
def test_issue_44_patch_only_incorrect_part_of_patch_should_raise_valuererror():
    with pytest.raises(ValidationError):
        DiffEntry(diff_content=SWE_FAILING_PART_OF_LARGER_PATCH)


# Empty lines must have a " " (SPACE) but this one does not, it fails
POOR_FORMAT_TWO_HUNK_DIFF = """\
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

# Empty lines must have a " " (SPACE) but this one does not, it fails
POOR_FORMAT_THREE_HUNK_DIFF = """\
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


@pytest.mark.pydantic_model
@pytest.mark.parametrize(
    "diff_content",
    [POOR_FORMAT_TWO_HUNK_DIFF, POOR_FORMAT_THREE_HUNK_DIFF],
)
def test_multihunk_with_poor_spacing_raises_errors(diff_content: str):
    with pytest.raises(ValueError):
        DiffEntry(diff_content=diff_content)


# Seen after most #44 changes, the lines don't match up
SWE_BENCH_OFFSET_HUNKS: str = """
diff --git a/django/db/backends/ddl_references.py b/django/db/backends/ddl_references.py
--- a/django/db/backends/ddl_references.py
+++ b/django/db/backends/ddl_references.py
@@ -84,8 +84,10 @@
     def __str__(self):
         def col_str(column, idx):
-            try:
-                return self.quote_name(column) + self.col_suffixes[idx]
-            except IndexError:
-                return self.quote_name(column)
+            try:
+                suffix = self.col_suffixes[idx]
+                return self.quote_name(column) + (' ' + suffix if suffix else '')
+            except IndexError:
+                return self.quote_name(column)
@@ -112,9 +114,13 @@
     def __str__(self):
         def col_str(column, idx):
             # Index.__init__() guarantees that self.opclasses is the same
             # length as self.columns.
-            col = '{} {}'.format(self.quote_name(column), self.opclasses[idx])
-            try:
-                col = '{} {}'.format(col, self.col_suffixes[idx])
-            except IndexError:
-                pass
+            col = self.quote_name(column)
+            op = self.opclasses[idx]
+            if op:
+                col = '{} {}'.format(col, op)
+            try:
+                suffix = self.col_suffixes[idx]
+                if suffix:
+                    col = '{} {}'.format(col, suffix)
+            except IndexError:
+                pass
             return col
"""


@pytest.mark.pydantic_model
def test_valid_format_but_poor_line_numbers_should_raise():
    with pytest.raises(ValueError):
        DiffEntry(diff_content=SWE_BENCH_OFFSET_HUNKS)


# The index hash 00000 is only ok for deletions or additions and never for file changes
SWE_OK_HUNKS_BUT_POOR_INDEX: str = """
diff --git a/lib/matplotlib/patches.py b/lib/matplotlib/patches.py
index 0000000..0000000 100644
--- a/lib/matplotlib/patches.py
+++ b/lib/matplotlib/patches.py
@@ -589,4 +589,3 @@
-        # Patch has traditionally ignored the dashoffset.
-        with cbook._setattr_cm(
-                 self, _dash_pattern=(0, self._dash_pattern[1])), \
-             self._bind_draw_path_function(renderer) as draw_path:
+        # Preserve the dash pattern (including offset) when drawing patches.
+        # Historically patches ignored the dash offset; allow it now.
+        with self._bind_draw_path_function(renderer) as draw_path:
"""


@pytest.mark.pydantic_model
def test_valid_hunks_but_index_doesnt_make_sense_should_raise():
    with pytest.raises(ValueError):
        DiffEntry(diff_content=SWE_OK_HUNKS_BUT_POOR_INDEX)


SWE_ANOTHER_POOR_HUNK_COUNTING: str = """
diff --git a/django/core/management/commands/makemigrations.py b/django/core/management/commands/makemigrations.py
--- a/django/core/management/commands/makemigrations.py
+++ b/django/core/management/commands/makemigrations.py
@@ -230,13 +230,16 @@
         )
-        # If --check was supplied, exit with non-zero status when there are changes
-        if check_changes and changes:
-            sys.exit(1)
-
-        if not changes:
+        # If --check was supplied, ensure we do not write migration files.
+        # Run in dry-run mode so the command still prints the expected
+        # migration summaries/paths (useful for --scriptable consumers).
+        if check_changes:
+            self.dry_run = True
+
+        if not changes:
"""


@pytest.mark.pydantic_model
def test_valid_format_but_poor_line_numbers_should_raise_variant_2():
    with pytest.raises(ValueError):
        DiffEntry(diff_content=SWE_ANOTHER_POOR_HUNK_COUNTING)


SWE_LARGE_SCIKIT_LEARN_EXAMPLE_WITH_POOR_HUNKS: str = '''
diff --git a/sklearn/linear_model/least_angle.py b/sklearn/linear_model/least_angle.py
--- a/sklearn/linear_model/least_angle.py
+++ b/sklearn/linear_model/least_angle.py
@@ -1482,31 +1482,38 @@
-    def fit(self, X, y, copy_X=True):
-        """Fit the model using X, y as training data.
-
-        Parameters
-        ----------
-        X : array-like, shape (n_samples, n_features)
-            training data.
-
-        y : array-like, shape (n_samples,)
-            target values. Will be cast to X's dtype if necessary
-
-        copy_X : boolean, optional, default True
-            If ``True``, X will be copied; else, it may be overwritten.
-
-        Returns
-        -------
-        self : object
-            returns an instance of self.
-        """
-        X, y = check_X_y(X, y, y_numeric=True)
-
-        X, y, Xmean, ymean, Xstd = LinearModel._preprocess_data(
-            X, y, self.fit_intercept, self.normalize, self.copy_X)
-        max_iter = self.max_iter
-
-        Gram = self.precompute
-
-        alphas_, active_, coef_path_, self.n_iter_ = lars_path(
-            X, y, Gram=Gram, copy_X=copy_X, copy_Gram=True, alpha_min=0.0,
-            method='lasso', verbose=self.verbose, max_iter=max_iter,
-            eps=self.eps, return_n_iter=True, positive=self.positive)
+    def fit(self, X, y, copy_X=None):
+        """Fit the model using X, y as training data.
+
+        Parameters
+        ----------
+        X : array-like, shape (n_samples, n_features)
+            training data.
+
+        y : array-like, shape (n_samples,)
+            target values. Will be cast to X's dtype if necessary
+
+        copy_X : boolean or None, optional (default=None)
+            If provided, this overrides the instance setting ``self.copy_X``.
+            If ``True``, X will be copied; else, it may be overwritten.
+
+        Returns
+        -------
+        self : object
+            returns an instance of self.
+        """
+        X, y = check_X_y(X, y, y_numeric=True)
+
+        if copy_X is None:
+            copy_X = self.copy_X
+
+        X, y, Xmean, ymean, Xstd = LinearModel._preprocess_data(
+            X, y, self.fit_intercept, self.normalize, copy_X)
+        max_iter = self.max_iter
+
+        Gram = self.precompute
+
+        alphas_, active_, coef_path_, self.n_iter_ = lars_path(
+            X, y, Gram=Gram, copy_X=copy_X, copy_Gram=True, alpha_min=0.0,
+            method='lasso', verbose=self.verbose, max_iter=max_iter,
+            eps=self.eps, return_n_iter=True, positive=self.positive)
'''


@pytest.mark.pydantic_model
def test_valid_format_but_poor_line_numbers_should_raise_variant_3():
    with pytest.raises(ValueError):
        DiffEntry(diff_content=SWE_LARGE_SCIKIT_LEARN_EXAMPLE_WITH_POOR_HUNKS)


MULTIFILE_TRAILING_ADDED_BLANKS = """\
diff --git a/a.txt b/a.txt
index 1111111..2222222 100644
--- a/a.txt
+++ b/a.txt
@@ -1,3 +1,5 @@
 line1
 line2
 line3
+
+
diff --git a/b.txt b/b.txt
index 3333333..4444444 100644
--- a/b.txt
+++ b/b.txt
@@ -1,1 +1,1 @@
-old
+new
"""

# Valid: added line at EOF without newline, using the proper sentinel.
MULTIFILE_TRAILING_ADDED_NO_EOFNL = """\
diff --git a/a.txt b/a.txt
index 1111111..2222222 100644
--- a/a.txt
+++ b/a.txt
@@ -1,3 +1,5 @@
 line1
 line2
 line3
+
+lastline
\\ No newline at end of file
diff --git a/b.txt b/b.txt
index 3333333..4444444 100644
--- a/b.txt
+++ b/b.txt
@@ -1,1 +1,1 @@
-old
+new
"""


@pytest.mark.pydantic_model
def test_multifile_trailing_added_line_without_final_newline_should_validate():
    assert _is_valid_patch(MULTIFILE_TRAILING_ADDED_NO_EOFNL) is True


# Valid: body contains text that looks like a header, encoded as context (leading space).
CONTEXT_LINE_THAT_LOOKS_LIKE_HEADER_TEXT = """\
diff --git a/x b/x
index abcd123..abcd124 100644
--- a/x
+++ b/x
@@ -1,3 +1,3 @@
 +++ this is real file content, not a header
-old
+new
 end
"""


@pytest.mark.pydantic_model
def test_context_line_that_looks_like_header_text_should_validate():
    assert _is_valid_patch(CONTEXT_LINE_THAT_LOOKS_LIKE_HEADER_TEXT) is True


# --- CRLF-focused cases -------------------------------------------------------

CRLF_NEW_FILE = (
    "diff --git a/crlf.txt b/crlf.txt\r\n"
    "new file mode 100644\r\n"
    "index 0000000..e69de29\r\n"
    "--- /dev/null\r\n"
    "+++ b/crlf.txt\r\n"
    "@@ -0,0 +1,3 @@\r\n"
    "+line1\r\n"
    "+line2\r\n"
    "+line3\r\n"
)


@pytest.mark.pydantic_model
def test_crlf_new_file_should_validate():
    assert _is_valid_patch(CRLF_NEW_FILE) is True


CRLF_MULTIFILE = (
    "diff --git a/a.txt b/a.txt\r\n"
    "index 1111111..2222222 100644\r\n"
    "--- a/a.txt\r\n"
    "+++ b/a.txt\r\n"
    "@@ -1,2 +1,3 @@\r\n"
    " line1\r\n"
    "-old\r\n"
    "+new\r\n"
    "+added\r\n"
    "diff --git a/b.txt b/b.txt\r\n"
    "index 3333333..4444444 100644\r\n"
    "--- a/b.txt\r\n"
    "+++ b/b.txt\r\n"
    "@@ -1,1 +1,1 @@\r\n"
    "-foo\r\n"
    "+bar\r\n"
)


@pytest.mark.pydantic_model
def test_crlf_multifile_should_validate():
    assert _is_valid_patch(CRLF_MULTIFILE) is True


# EOF without final newline; sentinel line uses CRLF
CRLF_NO_EOF_NL = (
    "diff --git a/eof.txt b/eof.txt\r\n"
    "index aaabbbb..ccccddd 100644\r\n"
    "--- a/eof.txt\r\n"
    "+++ b/eof.txt\r\n"
    "@@ -1,2 +1,3 @@\r\n"
    " stay\r\n"
    "-remove\r\n"
    "+keep\r\n"
    "+lastline\r\n"
    "\\ No newline at end of file\r\n"
)


@pytest.mark.pydantic_model
def test_crlf_no_final_newline_should_validate():
    assert _is_valid_patch(CRLF_NO_EOF_NL) is True


# Mixed endings: one stray '\r' remains in content while lines are '\n' separated.
MIXED_CRLF_WITH_STRAY_CR = (
    "diff --git a/mixed.txt b/mixed.txt\n"
    "index 9999999..aaaaaaa 100644\n"
    "--- a/mixed.txt\n"
    "+++ b/mixed.txt\n"
    "@@ -1,2 +1,2 @@\n"
    " line1\r\n"  # simulate CR kept on line
    "-old\n"
    "+new\n"
)


@pytest.mark.pydantic_model
def test_mixed_crlf_with_stray_carriage_returns_should_validate():
    assert _is_valid_patch(MIXED_CRLF_WITH_STRAY_CR) is True


# --- Section-boundary clipping on '+++ ' at column 0 --------------------------
# This reproduces a realistic file where an ADDED line literally starts with '+++'
# (it is content, not a header). According to unified-diff rules, this is valid.
ADDED_LINE_LOOKS_LIKE_HEADER = """\
diff --git a/h.txt b/h.txt
index 1111111..2222222 100644
--- a/h.txt
+++ b/h.txt
@@ -1,3 +1,4 @@
 line1
-old
+new
+++ not a header
 end
"""


@pytest.mark.pydantic_model
@pytest.mark.regression
def test_added_line_looks_like_header_should_validate():
    assert _is_valid_patch(ADDED_LINE_LOOKS_LIKE_HEADER) is True


# Variant with CRLF to ensure the same edge with Windows line endings.
ADDED_LINE_LOOKS_LIKE_HEADER_CRLF = (
    "diff --git a/h2.txt b/h2.txt\r\n"
    "index 1111111..2222222 100644\r\n"
    "--- a/h2.txt\r\n"
    "+++ b/h2.txt\r\n"
    "@@ -1,3 +1,4 @@\r\n"
    " line1\r\n"
    "-old\r\n"
    "+new\r\n"
    "+++ not a header\r\n"
    " end\r\n"
)


@pytest.mark.pydantic_model
@pytest.mark.regression
def test_added_line_looks_like_header_crlf_should_validate():
    assert _is_valid_patch(ADDED_LINE_LOOKS_LIKE_HEADER_CRLF) is True


# --- Trailing blank context at hunk end (boundary next file) ------------------
# Ensures a final context line that is visually blank (' ') is retained even at the boundary.
TRAILING_BLANK_CONTEXT_BEFORE_NEXT_FILE = """\
diff --git a/a.txt b/a.txt
index 1010101..2020202 100644
--- a/a.txt
+++ b/a.txt
@@ -1,3 +1,3 @@
 line1
-foo
+bar
     
diff --git a/b.txt b/b.txt
index 3030303..4040404 100644
--- a/b.txt
+++ b/b.txt
@@ -1,1 +1,1 @@
-x
+y
"""


@pytest.mark.pydantic_model
def test_trailing_blank_context_before_next_file_should_validate():
    assert _is_valid_patch(TRAILING_BLANK_CONTEXT_BEFORE_NEXT_FILE) is True


# Added/Context lines that look like headers or git markers --------------------

ADDED_LINE_STARTS_WITH_DIFF_GIT = """\
diff --git a/f.txt b/f.txt
index 1111111..2222222 100644
--- a/f.txt
+++ b/f.txt
@@ -1,2 +1,3 @@
 line1
+diff --git not a header
 line3
"""


def test_added_line_starts_with_diff_git_should_validate():
    assert _is_valid_patch(ADDED_LINE_STARTS_WITH_DIFF_GIT) is True


CONTEXT_LINE_STARTS_WITH_DIFF_GIT = """\
diff --git a/g.txt b/g.txt
index 1111111..2222222 100644
--- a/g.txt
+++ b/g.txt
@@ -1,3 +1,3 @@
 diff --git appears here but is context
-old
+new
 end
"""


def test_context_line_starts_with_diff_git_should_validate():
    assert _is_valid_patch(CONTEXT_LINE_STARTS_WITH_DIFF_GIT) is True


ADDED_LINE_PLUS_DASHES = """\
diff --git a/h3.txt b/h3.txt
index 1111111..2222222 100644
--- a/h3.txt
+++ b/h3.txt
@@ -1,3 +1,4 @@
 first
-old
+new
+--- definitely not a header
 end
"""


def test_added_line_that_looks_like_minus_header_should_validate():
    assert _is_valid_patch(ADDED_LINE_PLUS_DASHES) is True


CONTEXT_LINE_SPACE_THEN_PLUSSES = """\
diff --git a/h4.txt b/h4.txt
index 1111111..2222222 100644
--- a/h4.txt
+++ b/h4.txt
@@ -1,3 +1,3 @@
 +++ appears but as context
-old
+new
 end
"""


def test_context_line_with_three_pluses_should_validate():
    assert _is_valid_patch(CONTEXT_LINE_SPACE_THEN_PLUSSES) is True


# Multi-hunk with '+++ ' inside first hunk body --------------------------------
MULTIHUNK_WITH_TRICKY_ADDED_LINE = """\
diff --git a/multi.txt b/multi.txt
index aaaaaaaa..bbbbbbbb 100644
--- a/multi.txt
+++ b/multi.txt
@@ -1,3 +1,4 @@
 line1
-old
+new
+++ not a header
 end
@@ -10,2 +11,2 @@
 keep
-foo
+bar
"""


def test_multihunk_with_added_line_looks_like_header_should_validate():
    assert _is_valid_patch(MULTIHUNK_WITH_TRICKY_ADDED_LINE) is True


# CRLF variant of the above -----------------------------------------------------

MULTIHUNK_WITH_TRICKY_ADDED_LINE_CRLF = (
    "diff --git a/multicr.txt b/multicr.txt\r\n"
    "index aaaaaaaa..bbbbbbbb 100644\r\n"
    "--- a/multicr.txt\r\n"
    "+++ b/multicr.txt\r\n"
    "@@ -1,3 +1,4 @@\r\n"
    " line1\r\n"
    "-old\r\n"
    "+new\r\n"
    "+++ not a header\r\n"
    " end\r\n"
    "@@ -10,2 +11,2 @@\r\n"
    " keep\r\n"
    "-foo\r\n"
    "+bar\r\n"
)


def test_multihunk_with_tricky_added_line_crlf_should_validate():
    assert _is_valid_patch(MULTIHUNK_WITH_TRICKY_ADDED_LINE_CRLF) is True


# Trailing blank context line exactly at hunk end (LF + CRLF) ------------------

TRAILING_SINGLE_SPACE_CONTEXT_END = """\
diff --git a/tailctx.txt b/tailctx.txt
index 1010101..2020202 100644
--- a/tailctx.txt
+++ b/tailctx.txt
@@ -1,3 +1,3 @@
 head
-old
+new
     
"""


def test_trailing_single_space_context_line_should_validate():
    assert _is_valid_patch(TRAILING_SINGLE_SPACE_CONTEXT_END) is True


TRAILING_SINGLE_SPACE_CONTEXT_END_CRLF = (
    "diff --git a/tailctx2.txt b/tailctx2.txt\r\n"
    "index 1010101..2020202 100644\r\n"
    "--- a/tailctx2.txt\r\n"
    "+++ b/tailctx2.txt\r\n"
    "@@ -1,3 +1,3 @@\r\n"
    " head\r\n"
    "-old\r\n"
    "+new\r\n"
    "     \r\n"
)


def test_trailing_single_space_context_line_crlf_should_validate():
    assert _is_valid_patch(TRAILING_SINGLE_SPACE_CONTEXT_END_CRLF) is True


# Counter-example that must continue to pass after the change ------------------
# A normal two-file patch with no tricky lines. Ensures no regression in basics.

PLAIN_TWO_FILE_PATCH = """\
diff --git a/a.txt b/a.txt
index aaaa111..bbbb222 100644
--- a/a.txt
+++ b/a.txt
@@ -1,2 +1,2 @@
-old
+new
 end
diff --git a/b.txt b/b.txt
index cccc333..dddd444 100644
--- a/b.txt
+++ b/b.txt
@@ -1,1 +1,1 @@
-foo
+bar
"""


def test_plain_two_file_patch_should_validate():
    assert _is_valid_patch(PLAIN_TWO_FILE_PATCH) is True
