from pathlib import Path

import pytest

from useagent.tools.git import find_merge_conflicts


def _create_file(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


@pytest.mark.tool
def test_single_file_with_conflict(tmp_path: Path):
    f = _create_file(tmp_path / "conflict.txt", "<<<<<<< HEAD\nconflict\n=======")
    result = find_merge_conflicts(tmp_path)
    assert [Path(r) for r in result] == [f]


@pytest.mark.tool
def test_multiple_files_with_and_without_conflicts(tmp_path: Path):
    _create_file(tmp_path / "clean1.txt", "no conflict")
    f2 = _create_file(tmp_path / "conflict1.txt", "<<<<<<< HEAD\nconflict")
    f3 = _create_file(tmp_path / "conflict2.txt", "<<<<<<< HEAD\nconflict")
    result = find_merge_conflicts(tmp_path)
    assert {Path(r) for r in result} == {f2, f3}


@pytest.mark.tool
def test_nested_directory_with_conflict(tmp_path: Path):
    sub = tmp_path / "subdir"
    sub.mkdir()
    _create_file(tmp_path / "clean.txt", "no conflict")
    f2 = _create_file(sub / "conflict.txt", "<<<<<<< HEAD\nconflict")
    result = find_merge_conflicts(tmp_path)
    assert {Path(r) for r in result} == {f2}


@pytest.mark.tool
def test_empty_directory(tmp_path: Path):
    result = find_merge_conflicts(tmp_path)
    assert result == []


@pytest.mark.tool
def test_nonexistent_directory_raises():
    with pytest.raises(ValueError):
        find_merge_conflicts(Path("/nonexistent/fakepath"))


@pytest.mark.tool
def test_file_input_raises(tmp_path: Path):
    f = _create_file(tmp_path / "somefile.txt", "<<<<<<< HEAD\nconflict")
    with pytest.raises(ValueError):
        find_merge_conflicts(f)
