import pytest

from useagent.pydantic_models.artifacts.git import DiffEntry
from useagent.pydantic_models.output.code_change import CodeChange

NEW_FILE_ONE_LINE = """\
diff --git a/newfile.txt b/newfile.txt
new file mode 100644
index 0000000..e69de29
--- /dev/null
+++ b/newfile.txt
@@
+Hello world
"""


@pytest.fixture
def valid_diff_entry() -> DiffEntry:
    return DiffEntry(NEW_FILE_ONE_LINE)


@pytest.mark.parametrize("bad_str", ["", " ", "   ", "\n", "\t"])
@pytest.mark.pydantic_model
def test_constructor_should_raise_on_invalid_explanation(
    bad_str: str, valid_diff_entry: DiffEntry
):
    with pytest.raises(ValueError):
        CodeChange(explanation=bad_str, change=valid_diff_entry, doubts="valid")


@pytest.mark.parametrize("bad_str", ["", " ", "   ", "\n", "\t"])
@pytest.mark.pydantic_model
def test_constructor_should_raise_on_invalid_doubts(
    bad_str: str, valid_diff_entry: DiffEntry
):
    with pytest.raises(ValueError):
        CodeChange(explanation="valid", change=valid_diff_entry, doubts=bad_str)


@pytest.mark.pydantic_model
def test_constructor_should_allow_none_doubts(valid_diff_entry: DiffEntry):
    c = CodeChange(explanation="valid", change=valid_diff_entry, doubts=None)
    assert isinstance(c, CodeChange)


@pytest.mark.pydantic_model
def test_get_output_instructions_should_not_return_none():
    assert CodeChange.get_output_instructions() is not None
