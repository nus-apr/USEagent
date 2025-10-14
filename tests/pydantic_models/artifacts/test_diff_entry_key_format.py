import pytest
from pydantic import TypeAdapter

from useagent.pydantic_models.artifacts.git.diff import DiffEntry
from useagent.pydantic_models.artifacts.git.diff_store import DiffEntryKey, DiffStore

_ADAPTER = TypeAdapter(DiffEntryKey)
EXAMPLE_GIT_DIFF: str = """\
diff --git a/a b/a
new file mode 100644
index 0000000..deadbee
--- /dev/null
+++ b/a
@@ -0,0 +1 @@
+Hello world
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


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("diff_0", "diff_0"),
        ("  diff_12  ", "diff_12"),
        ("DIFF_34", "diff_34"),
        ("\tdiff_567\n", "diff_567"),
    ],
)
def test_diffentrykey_validate_should_normalize_and_accept(raw: str, expected: str):
    assert _ADAPTER.validate_python(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "diff_-1",
        "diff_",
        "diff_x",
        "dif_0",
        "diff_1.2",
        "diff_01a",
        "random",
        "",
        "   ",
    ],
)
def test_diffentrykey_validate_should_reject_invalid_patterns(raw: str):
    with pytest.raises(ValueError):
        _ADAPTER.validate_python(raw)


def test_diffentrykey_validate_should_reject_non_string():
    with pytest.raises(TypeError):
        _ADAPTER.validate_python(123)  # type: ignore[arg-type]


@pytest.mark.pydantic_model
def test_add_entry_should_return_valid_normalized_diffentrykey():
    store = DiffStore()
    k = store._add_entry(DiffEntry(diff_content=EXAMPLE_GIT_DIFF))
    # validates and round-trips
    assert _ADAPTER.validate_python(k) == k


def test_entry_with_diff_0_should_be_valid():
    # DevNote: The diff_0 is especially important,
    # at one point we discussed positive integers and I think it flawed the chance to get diff_0
    # because gpt does not think 0 is positive (fair enough)
    _ADAPTER.validate_python("diff_0")
    pass
