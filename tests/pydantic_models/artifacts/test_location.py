import pytest
from pydantic import ValidationError

from useagent.pydantic_models.artifacts.code import Location


@pytest.mark.pydantic_model
@pytest.mark.parametrize(
    "rel_file_path", ["src/main.py", "./main.py", "sub/dir/file.py"]
)
@pytest.mark.parametrize("start_line,end_line", [(1, 2), (5, 10), (100, 200)])
@pytest.mark.parametrize("code_content", ["print('x')", "x = 1", "def foo(): pass"])
def test_valid_locations(rel_file_path, start_line, end_line, code_content):
    Location(
        rel_file_path=rel_file_path,
        start_line=start_line,
        end_line=end_line,
        code_content=code_content,
        reason_why_relevant="valid test",
    )


@pytest.mark.pydantic_model
@pytest.mark.parametrize("rel_file_path", ["", " ", "\n", "/abs/path/file.py"])
def test_invalid_rel_file_path(rel_file_path):
    with pytest.raises(ValidationError):
        Location(
            rel_file_path=rel_file_path,
            start_line=1,
            end_line=2,
            code_content="x = 1",
            reason_why_relevant="fail",
        )


@pytest.mark.pydantic_model
@pytest.mark.parametrize("start_line,end_line", [(0, 2), (1, -1)])
def test_invalid_line_numbers(start_line, end_line):
    with pytest.raises(ValidationError):
        Location(
            rel_file_path="file.py",
            start_line=start_line,
            end_line=end_line,
            code_content="x = 1",
            reason_why_relevant="fail",
        )


@pytest.mark.pydantic_model
@pytest.mark.parametrize("code_content", ["", " ", "\n"])
def test_invalid_code_content(code_content):
    with pytest.raises(ValidationError):
        Location(
            rel_file_path="file.py",
            start_line=1,
            end_line=2,
            code_content=code_content,
            reason_why_relevant="fail",
        )


@pytest.mark.pydantic_model
def test_invalid_line_order():
    with pytest.raises(ValidationError):
        Location(
            rel_file_path="main.py",
            start_line=20,
            end_line=10,
            code_content="print()",
            reason_why_relevant="fail",
        )
