import subprocess
from pathlib import Path

import pytest

from useagent.pydantic_models.artifacts.git import DiffEntry
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo
from useagent.tools.git import _commit_exists, _view_commit_as_diff

REPO_URL = "https://github.com/octocat/Hello-World.git"


def clone_repo(target: Path) -> Path:
    subprocess.run(
        ["git", "clone", "--no-single-branch", REPO_URL, str(target)], check=True
    )
    return target


def init_git_repo(repo_path: Path) -> str:
    subprocess.run(["git", "init"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True
    )
    file = repo_path / "file.txt"
    file.write_text("initial\n")
    subprocess.run(["git", "add", "file.txt"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_path, check=True)
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo_path, text=True
    ).strip()


@pytest.mark.tool
def test_setup_git_show_format_patch_output(tmp_path: Path):
    # DevNote: This was for me to figure out what I have to use as a command,
    # but it also shows that my `clone_repo` behave as intended.
    repo = clone_repo(tmp_path / "repo")
    commit = "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d"
    result = subprocess.run(
        ["git", "show", "-m", "--pretty=format:", "--patch", commit],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    print("STDOUT:\n", result.stdout)
    print("STDERR:\n", result.stderr)
    assert result.returncode == 0
    assert result.stdout.strip() != ""


@pytest.mark.tool
def test_valid_commit_returns_diff(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)
    (repo / "file.txt").write_text("initial\nchanged\n")
    subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "second"], cwd=repo, check=True)
    new_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()

    result = _view_commit_as_diff(repo, new_commit)
    assert isinstance(result, DiffEntry)


@pytest.mark.tool
def test_nonexistent_commit_returns_tool_error(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)
    result = _view_commit_as_diff(repo, "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef")
    assert isinstance(result, ToolErrorInfo)


@pytest.mark.tool
def test_not_a_git_repo_returns_tool_error(tmp_path: Path):
    nonrepo = tmp_path / "nonrepo"
    nonrepo.mkdir()
    result = _view_commit_as_diff(nonrepo, "HEAD")
    assert isinstance(result, ToolErrorInfo)


@pytest.mark.tool
def test_invalid_path_returns_tool_error(tmp_path: Path):
    invalid = tmp_path / "notexist"
    result = _view_commit_as_diff(invalid, "HEAD")
    assert isinstance(result, ToolErrorInfo)


@pytest.mark.tool
@pytest.mark.online
def test_known_commit_7fd1_which_is_merge_commit_gives_diff_entry(tmp_path: Path):
    repo = clone_repo(tmp_path / "repo")
    result = _view_commit_as_diff(repo, "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d")
    assert isinstance(result, DiffEntry)


@pytest.mark.tool
@pytest.mark.online
def test_known_commit_553c_non_merge_commit_gives_diff_entry(tmp_path: Path):
    repo = clone_repo(tmp_path / "repo")
    result = _view_commit_as_diff(repo, "553c2077f0edc3d5dc5d17262f6aa498e69d6f8e")
    assert isinstance(result, DiffEntry)


@pytest.mark.tool
@pytest.mark.online
def test_retrieving_HEAD_command_should_be_a_supported_commit_reference(tmp_path: Path):
    repo = clone_repo(tmp_path / "repo")
    result = _view_commit_as_diff(repo, "HEAD")
    assert isinstance(result, DiffEntry)


@pytest.mark.tool
@pytest.mark.online
def test_retrieving_HEAD_minus_one_command_should_be_a_supported_commit_reference(
    tmp_path: Path,
):
    repo = clone_repo(tmp_path / "repo")
    result = _view_commit_as_diff(repo, "HEAD~1")
    assert isinstance(result, DiffEntry)


@pytest.mark.tool
@pytest.mark.online
def test_diff_content_differs_between_HEAD_and_7fd1(tmp_path: Path):
    # As of 29.07.2025, 7fd1 IS the HEAD of the octocat hello world.
    repo = clone_repo(tmp_path / "repo")
    head = _view_commit_as_diff(repo, "HEAD")
    old = _view_commit_as_diff(repo, "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d")
    assert isinstance(head, DiffEntry)
    assert isinstance(old, DiffEntry)
    assert head == old


@pytest.mark.tool
@pytest.mark.online
def test_known_commit_7fd1_abbreviated(tmp_path: Path):
    repo = clone_repo(tmp_path / "repo")
    result = _view_commit_as_diff(repo, "7fd1a6")
    assert isinstance(result, DiffEntry)


@pytest.mark.tool
@pytest.mark.online
def test_known_commit_553c_abbreviated(tmp_path: Path):
    repo = clone_repo(tmp_path / "repo")
    result = _view_commit_as_diff(repo, "553c20")
    assert isinstance(result, DiffEntry)


@pytest.mark.tool
def test_merge_commit_without_changes_returns_a_valid_diffEntry(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo, check=True
    )
    (repo / "file.txt").write_text("base\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True)

    # Create two identical branches from the same commit
    subprocess.run(["git", "checkout", "-b", "branch1"], cwd=repo, check=True)
    subprocess.run(
        ["git", "checkout", "-b", "branch2", "branch1"], cwd=repo, check=True
    )

    # Merge branch1 into branch2 with no changes
    subprocess.run(["git", "checkout", "branch2"], cwd=repo, check=True)
    subprocess.run(
        ["git", "merge", "branch1", "--no-ff", "-m", "merge identical branches"],
        cwd=repo,
        check=True,
    )

    # The merge should contain no diff
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()
    result = _view_commit_as_diff(repo, commit)
    assert isinstance(result, DiffEntry)


@pytest.mark.tool
def test_commit_with_deletion(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)
    (repo / "file.txt").unlink()
    subprocess.run(["git", "rm", "file.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "delete file"], cwd=repo, check=True)
    new_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()

    result = _view_commit_as_diff(repo, new_commit)
    assert isinstance(result, DiffEntry)


@pytest.mark.tool
def test_commit_with_amend_but_no_diff(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)
    subprocess.run(
        ["git", "commit", "--amend", "-m", "same content new msg"], cwd=repo, check=True
    )
    new_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()
    result = _view_commit_as_diff(repo, new_commit)
    assert isinstance(result, DiffEntry)


@pytest.mark.tool
def test_commit_with_whitespace_change(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)
    (repo / "file.txt").write_text("initial\n\n")  # Add trailing newline
    subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "whitespace only"], cwd=repo, check=True)
    new_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()
    result = _view_commit_as_diff(repo, new_commit)
    assert isinstance(result, DiffEntry)


@pytest.mark.tool
def test_commit_exists_true(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    commit = init_git_repo(repo)
    assert _commit_exists(repo, commit) is True


@pytest.mark.tool
def test_commit_exists_false(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)
    assert _commit_exists(repo, "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef") is False


@pytest.mark.tool
def test_commit_exists_with_abbreviation(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    full = init_git_repo(repo)
    short = full[:8]
    assert _commit_exists(repo, short) is True


@pytest.mark.tool
def test_commit_exists_invalid_path(tmp_path: Path):
    nonrepo = tmp_path / "nonrepo"
    nonrepo.mkdir()
    assert _commit_exists(nonrepo, "HEAD") is False
