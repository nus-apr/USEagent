import pytest
import subprocess
from pathlib import Path
from useagent.tasks.github_task import GithubTask


@pytest.mark.parametrize("bad_value", [None, "", "   ", "\n", "\t"])
def test_invalid_issue_statement_raises(bad_value, tmp_path):
    with pytest.raises(ValueError):
        GithubTask(bad_value, "https://github.com/example/repo.git", tmp_path / "dest")

@pytest.mark.parametrize("bad_value", [None, "", "   ", "\n", "\t", "ftp://wrong.com/repo.git"])
def test_invalid_repo_url_raises(bad_value, tmp_path):
    with pytest.raises(ValueError):
        GithubTask("Issue", bad_value, tmp_path / "dest")

def test_invalid_working_dir_raises(tmp_path):
    with pytest.raises(ValueError):
        GithubTask("Issue", "https://github.com/example/repo.git", None)

def test_clone_into_directory(tmp_path):
    repo_path = tmp_path / "repo"
    subprocess.run(["git", "init", "--bare", str(repo_path)], check=True)

    clone_path = tmp_path / "cloned"
    task = GithubTask("Issue", f"file://{repo_path}", clone_path)

    assert (clone_path / "HEAD").exists() or (clone_path / ".git").exists()

def test_overwrites_existing_dir(tmp_path):
    repo_path = tmp_path / "repo"
    subprocess.run(["git", "init", str(repo_path)], check=True)
    (repo_path / "file.txt").write_text("content")
    subprocess.run(["git", "add", "file.txt"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_path, check=True)

    target_dir = tmp_path / "clone"
    target_dir.mkdir()
    (target_dir / "old.txt").write_text("old")

    task = GithubTask("Issue", f"file://{repo_path}", target_dir)

    assert not (target_dir / "old.txt").exists()
    assert (target_dir / "file.txt").exists()

def test_get_working_directory_returns_correct_path(tmp_path):
    repo_path = tmp_path / "repo"
    subprocess.run(["git", "init", "--bare", str(repo_path)], check=True)

    dest = tmp_path / "workdir"
    task = GithubTask("Issue", f"file://{repo_path}", dest)
    assert task.get_working_directory() == dest

@pytest.mark.parametrize("url", [
    "https://github.com/octocat/Hello-World.git",
    "git@github.com:octocat/Hello-World.git"
])
def test_clone_public_github_repo(tmp_path, url):
    dest = tmp_path / "octocat"
    task = GithubTask("Issue", url, dest)
    assert (dest / "README").exists() or (dest / "README.md").exists()
    assert (dest / ".git").exists()

@pytest.mark.parametrize("url", [
    "https://github.com/octocat/Hello-World.git",
    "git@github.com:octocat/Hello-World.git"
])
def test_public_github_repo_git_log(tmp_path, url):
    dest = tmp_path / "octocatlog"
    task = GithubTask("Issue", url, dest)
    result = subprocess.run(["git", "log"], cwd=dest, stdout=subprocess.PIPE, check=True)
    assert b"commit" in result.stdout

@pytest.mark.parametrize("url", [
    "https://github.com/octocat/Hello-World.git",
    "git@github.com:octocat/Hello-World.git"
])
def test_working_directory_has_files(tmp_path, url):
    dest = tmp_path / "octocatfiles"
    task = GithubTask("Issue", url, dest)
    contents = list(dest.glob("*"))
    assert len(contents) > 0


@pytest.mark.parametrize("url,expected", [
    ("https://github.com/octocat/Hello-World.git", "octocat_hello_world"),
    ("git@github.com:octocat/Hello-World.git", "octocat_hello_world"),
    ("https://github.com/user/repo-name.git", "user_repo_name"),
    ("git@github.com:user/repo.name.git", "user_repo_name"),
    ("https://example.com/some/path/to/repo.git", "some_path_to_repo"),
])
def test_uid_derivation_from_url(url, expected):
    assert GithubTask._derive_uid_from_url(url) == expected
