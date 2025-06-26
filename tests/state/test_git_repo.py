import os
import shutil
import subprocess
from pathlib import Path

import pytest

from useagent.state.git_repo import GitRepository

def test_initialize_git_if_needed(tmp_path):
    (tmp_path / "file1.txt").write_text("hello")
    (tmp_path / "file2.txt").write_text("world")

    repo = GitRepository(str(tmp_path))

    git_dir = tmp_path / ".git"
    assert git_dir.is_dir()

    log = subprocess.check_output(["git", "log", "--oneline"], cwd=tmp_path).decode()
    assert "Initial commit" in log

def test_repo_make_and_clean_changes(tmp_path):
    (tmp_path / "file1.txt").write_text("original")
    repo = GitRepository(str(tmp_path))

    (tmp_path / "file1.txt").write_text("changed")
    (tmp_path / "file2.txt").write_text("new")

    repo.repo_clean_changes()

    assert not (tmp_path / "file2.txt").exists()
    assert (tmp_path / "file1.txt").read_text() == "original"

def test_init_for_existing_git_repo(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    (tmp_path / "file.txt").write_text("existing")
    subprocess.run(["git", "add", "file.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "Pre-existing commit"], cwd=tmp_path, check=True)

    repo = GitRepository(str(tmp_path))

    log = subprocess.check_output(["git", "log", "--oneline"], cwd=tmp_path).decode()
    assert "Pre-existing commit" in log

def test_clean_changes_noop(tmp_path):
    (tmp_path / "file.txt").write_text("content")
    repo = GitRepository(str(tmp_path))

    before = subprocess.check_output(["git", "status", "--porcelain"], cwd=tmp_path)
    repo.repo_clean_changes()
    after = subprocess.check_output(["git", "status", "--porcelain"], cwd=tmp_path)

    assert before == after == b""

def test_git_diff_additions_after_initialization_git_diff_will_show_files(tmp_path):
    (tmp_path / "a.txt").write_text("A")
    (tmp_path / "b.txt").write_text("B")
    repo = GitRepository(str(tmp_path))

    (tmp_path / "a.txt").write_text("A-modified")
    (tmp_path / "c.txt").write_text("C-new")

    diff = subprocess.check_output(["git", "diff"], cwd=tmp_path).decode()
    status = subprocess.check_output(["git", "status"], cwd=tmp_path).decode()
    assert "Untracked files" in status
    assert "c.txt" in status


def test_gitignore_prevents_tracking(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("ignored.txt\n")
    (tmp_path / "tracked.txt").write_text("tracked\n")
    (tmp_path / "ignored.txt").write_text("ignore me\n")

    repo = GitRepository(str(tmp_path))

    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=tmp_path).decode()
    assert "ignored.txt" not in status
    assert "tracked.txt" not in status  # committed by repo init


def test_gitignore_file_is_not_committed(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("*.log\n")
    (tmp_path / "example.log").write_text("log line\n")
    (tmp_path / "data.txt").write_text("important\n")

    repo = GitRepository(str(tmp_path))

    log = subprocess.check_output(["git", "log", "--oneline"], cwd=tmp_path).decode()
    ls_files = subprocess.check_output(["git", "ls-files"], cwd=tmp_path).decode()

    assert "example.log" not in ls_files
    assert "data.txt" in ls_files


def test_gitignore_directory(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("temp_dir/\n")
    temp_dir = tmp_path / "temp_dir"
    temp_dir.mkdir()
    (temp_dir / "tmp.txt").write_text("should be ignored\n")
    (tmp_path / "keep.txt").write_text("tracked\n")

    repo = GitRepository(str(tmp_path))

    tracked = subprocess.check_output(["git", "ls-files"], cwd=tmp_path).decode()
    assert "keep.txt" in tracked
    assert "temp_dir/tmp.txt" not in tracked
