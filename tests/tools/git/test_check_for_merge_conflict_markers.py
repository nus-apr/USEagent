from pathlib import Path

import pytest

from useagent.tools.git import check_for_merge_conflict_markers


@pytest.mark.tool
def create_file(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


@pytest.mark.tool
def test_file_with_merge_markers(tmp_path: Path):
    f = create_file(
        tmp_path / "conflict.txt",
        "<<<<<<< HEAD\nconflict\n=======\nother\n>>>>>>> branch",
    )
    assert check_for_merge_conflict_markers(f)


@pytest.mark.tool
def test_file_without_merge_markers(tmp_path: Path):
    f = create_file(
        tmp_path / "clean.txt", "This is a normal file.\nNo conflicts here."
    )
    assert not check_for_merge_conflict_markers(f)


@pytest.mark.tool
def test_file_with_partial_marker(tmp_path: Path):
    # We only consider merge conflicts that START with the markers, if they are somewhere inside it I don't care.
    f = create_file(tmp_path / "partial.txt", "This line has <<<<<<< but nothing else.")
    assert not check_for_merge_conflict_markers(f)


@pytest.mark.tool
def test_empty_file(tmp_path: Path):
    f = create_file(tmp_path / "empty.txt", "")
    assert not check_for_merge_conflict_markers(f)


@pytest.mark.tool
def test_file_with_marker_like_but_not_start(tmp_path: Path):
    f = create_file(tmp_path / "not_marker.txt", "code <<<<<<< HEAD is inline")
    assert not check_for_merge_conflict_markers(f)


@pytest.mark.tool
def test_nonexistent_file_raises(tmp_path: Path):
    p = tmp_path / "missing.txt"
    with pytest.raises(ValueError):
        check_for_merge_conflict_markers(p)


@pytest.mark.tool
def test_directory_input_raises(tmp_path: Path):
    with pytest.raises(ValueError):
        check_for_merge_conflict_markers(tmp_path)


@pytest.mark.tool
def test_line_with_marker_not_at_start(tmp_path: Path):
    f = create_file(
        tmp_path / "inline_marker.txt", "code before >>>>>>> marker\nanother line"
    )
    assert not check_for_merge_conflict_markers(f)


@pytest.mark.tool
def test_doubled_merge_marker(tmp_path: Path):
    doubled = "<<<<<<<<< HEAD\nconflict\n========\nother\n>>>>>>>>> branch"
    f = create_file(tmp_path / "doubled_marker.txt", doubled)
    assert check_for_merge_conflict_markers(f)


@pytest.mark.tool
def test_incomplete_merge_marker(tmp_path: Path):
    content = "<<<<<<\nthis is not a full marker"
    f = create_file(tmp_path / "incomplete_marker.txt", content)
    assert not check_for_merge_conflict_markers(f)


### Edge Cases
### Currently not supported !
@pytest.mark.tool
def test_python_multiline_string_with_marker(tmp_path: Path):
    content = '''def example():\n    s = """\n<<<<<<< HEAD\ninside string\n=======\nother\n>>>>>>>\n"""\n    return s'''
    f = create_file(tmp_path / "code_with_string.py", content)
    assert check_for_merge_conflict_markers(f)


@pytest.mark.tool
def test_readme_with_code_block_marker(tmp_path: Path):
    content = "```bash\n<<<<<<< HEAD\nsome shell\n=======\nother\n>>>>>>>\n```"
    f = create_file(tmp_path / "README.md", content)
    assert check_for_merge_conflict_markers(f)
