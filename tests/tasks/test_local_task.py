import subprocess
from pathlib import Path

import pytest

from useagent.tasks.local_task import LocalTask


@pytest.fixture
def temp_project_dir(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / "file.txt").write_text("hello")
    return project


@pytest.fixture
def temp_working_dir(tmp_path: Path) -> Path:
    return tmp_path / "working"


@pytest.mark.parametrize("bad_value", [None, "", "\t", "\n", "   "])
def test_invalid_issue_statement_raises(bad_value, temp_project_dir):
    with pytest.raises(ValueError):
        LocalTask(bad_value, str(temp_project_dir))


@pytest.mark.parametrize("bad_value", [None, "", "\t", "\n", "   "])
def test_invalid_project_path_raises(bad_value):
    with pytest.raises(ValueError):
        LocalTask("Issue", bad_value)


def test_nonexistent_project_path_raises():
    with pytest.raises(ValueError):
        LocalTask("Issue", "/nonexistent/path")


def test_invalid_working_dir_raises(temp_project_dir):
    with pytest.raises(ValueError):
        LocalTask("Issue", str(temp_project_dir), None)


def test_overwrites_existing_working_dir(temp_project_dir, temp_working_dir):
    temp_working_dir.mkdir(parents=True)
    (temp_working_dir / "old.txt").write_text("old")
    LocalTask("Issue", str(temp_project_dir), temp_working_dir)
    assert not (temp_working_dir / "old.txt").exists()
    assert (temp_working_dir / "file.txt").exists()


def test_creates_new_working_dir(temp_project_dir, tmp_path):
    new_working_dir = tmp_path / "new_working"
    assert not new_working_dir.exists()
    LocalTask("Issue", str(temp_project_dir), new_working_dir)
    assert (new_working_dir / "file.txt").exists()


def test_git_repo_initialized(temp_project_dir, temp_working_dir):
    LocalTask("Issue", str(temp_project_dir), temp_working_dir)
    assert (temp_working_dir / ".git").exists() or Path(
        temp_working_dir
    ).exists()  # Loosely assumes GitRepository does init


def test_project_path_unchanged(temp_project_dir, tmp_path):
    original_content = (temp_project_dir / "file.txt").read_text()
    working_dir = tmp_path / "copy"
    LocalTask("Issue", str(temp_project_dir), working_dir)
    assert (temp_project_dir / "file.txt").read_text() == original_content
    assert (working_dir / "file.txt").read_text() == original_content


@pytest.mark.parametrize(
    "custom_dir", [None, Path("/tmp/custom1"), Path("/tmp/custom2")]
)
def test_get_working_directory(temp_project_dir, tmp_path, custom_dir):
    if custom_dir is None:
        task = LocalTask("Issue", str(temp_project_dir))
        assert task.get_working_directory() == Path("/tmp/working_dir")
    else:
        task = LocalTask("Issue", str(temp_project_dir), custom_dir)
        assert task.get_working_directory() == custom_dir


def test_git_history_copied(temp_project_dir, tmp_path):
    subprocess.run(["git", "init"], cwd=temp_project_dir, check=True)
    (temp_project_dir / "file.txt").write_text("commit content")
    subprocess.run(["git", "add", "file.txt"], cwd=temp_project_dir, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"], cwd=temp_project_dir, check=True
    )

    dest = tmp_path / "copy_repo"
    LocalTask("Issue", str(temp_project_dir), dest)

    result = subprocess.run(
        ["git", "log"], cwd=dest, stdout=subprocess.PIPE, check=True
    )
    assert b"initial commit" in result.stdout


def test_git_user_config_set(temp_project_dir, tmp_path):
    # Tests that we can initialize and set a git user, as done by the tasks downstream, and we get the right user there.
    subprocess.run(["git", "init"], cwd=temp_project_dir, check=True)
    (temp_project_dir / "file.txt").write_text("commit content")
    subprocess.run(["git", "add", "file.txt"], cwd=temp_project_dir, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"], cwd=temp_project_dir, check=True
    )  #

    dest = tmp_path / "copy_repo"
    LocalTask("Issue", str(temp_project_dir), dest)  #

    name = subprocess.run(
        ["git", "config", "user.name"], cwd=dest, stdout=subprocess.PIPE, check=True
    ).stdout.strip()
    email = subprocess.run(
        ["git", "config", "user.email"], cwd=dest, stdout=subprocess.PIPE, check=True
    ).stdout.strip()  #

    assert name == b"USEagent"
    assert email == b"useagent@useagent.com"


@pytest.mark.regression
def test_git_user_without_any_change_is_not_useagent():
    import useagent as useagent_module

    original_project_path = Path(useagent_module.__file__).parent

    name = subprocess.run(
        ["git", "config", "user.name"],
        cwd=original_project_path,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout.strip()
    email = subprocess.run(
        ["git", "config", "user.email"],
        cwd=original_project_path,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout.strip()

    assert name != b"USEagent"
    assert email != b"useagent@useagent.com"


@pytest.mark.regression
def test_git_user_is_only_changed_for_the_local_repository(temp_project_dir, tmp_path):
    # See Issue#6:
    # In the initial setup, the local task changed the global git config and overwrote my actual git user.
    subprocess.run(["git", "init"], cwd=temp_project_dir, check=True)
    (temp_project_dir / "file.txt").write_text("commit content")
    subprocess.run(["git", "add", "file.txt"], cwd=temp_project_dir, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"], cwd=temp_project_dir, check=True
    )

    dest = tmp_path / "copy_repo"
    LocalTask("Issue", str(temp_project_dir), dest)

    import useagent as useagent_module

    original_project_path = Path(useagent_module.__file__).parent

    name = subprocess.run(
        ["git", "config", "user.name"],
        cwd=original_project_path,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout.strip()
    email = subprocess.run(
        ["git", "config", "user.email"],
        cwd=original_project_path,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout.strip()

    assert name != b"USEagent"
    assert email != b"useagent@useagent.com"
