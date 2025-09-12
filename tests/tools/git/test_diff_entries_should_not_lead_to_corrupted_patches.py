# tests/tools/git/test_extract_diff_patch_apply.py
import subprocess
from pathlib import Path

import pytest

from useagent.pydantic_models.artifacts.git import DiffEntry
from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.state.git_repo import GitRepository
from useagent.tools.git import extract_diff


@pytest.mark.integration
@pytest.mark.tool
@pytest.mark.asyncio
async def test_change_patch_from_repo_a_applies_to_repo_b_should_modify_file(
    tmp_path: Path,
):
    repo_a = tmp_path / "repo_a"
    repo_a.mkdir(parents=True, exist_ok=True)
    (repo_a / "test.txt").write_text("original content\n")
    GitRepository(str(repo_a))
    (repo_a / "test.txt").write_text("original content\nnew line\n")

    diff_result = await extract_diff(project_dir=repo_a)
    assert isinstance(diff_result, DiffEntry)
    patch = diff_result.diff_content
    assert patch.startswith("diff --git ")
    assert "+new line" in patch
    patch_path = tmp_path / "change.patch"
    patch_path.write_text(patch)
    print(patch)

    repo_b = tmp_path / "repo_b"
    repo_b.mkdir(parents=True, exist_ok=True)
    (repo_b / "test.txt").write_text("original content\n")
    GitRepository(str(repo_b))
    assert (repo_b / "test.txt").read_text() == "original content\n"

    subprocess.run(["git", "apply", str(patch_path)], cwd=repo_b, check=True)
    assert (repo_b / "test.txt").read_text() == "original content\nnew line\n"


@pytest.mark.integration
@pytest.mark.tool
@pytest.mark.asyncio
async def test_new_file_patch_identical_baseline_should_create_file(tmp_path: Path):
    repo_a = tmp_path / "repo_a_newfile_same"
    repo_a.mkdir(parents=True, exist_ok=True)
    (repo_a / "base.txt").write_text("base\n")
    GitRepository(str(repo_a))
    (repo_a / "test.txt").write_text("hello\n")
    subprocess.run(["git", "add", "test.txt"], cwd=repo_a, check=True)

    diff_result = await extract_diff(project_dir=repo_a)
    patch = diff_result.diff_content
    assert "test.txt" in patch
    (tmp_path / "newfile_same.patch").write_text(patch)

    repo_b = tmp_path / "repo_b_newfile_same"
    repo_b.mkdir(parents=True, exist_ok=True)
    (repo_b / "base.txt").write_text("base\n")
    GitRepository(str(repo_b))
    assert not (repo_b / "test.txt").exists()

    print(patch)
    subprocess.run(
        ["git", "apply", str(tmp_path / "newfile_same.patch")], cwd=repo_b, check=True
    )
    assert (repo_b / "test.txt").read_text() == "hello\n"


@pytest.mark.integration
@pytest.mark.tool
@pytest.mark.asyncio
async def test_new_file_patch_different_baseline_should_create_file(tmp_path: Path):
    repo_a = tmp_path / "repo_a_newfile_diff"
    repo_a.mkdir(parents=True, exist_ok=True)
    (repo_a / "only-in-a.txt").write_text("A\n")
    GitRepository(str(repo_a))
    (repo_a / "test.txt").write_text("payload\n")
    subprocess.run(["git", "add", "test.txt"], cwd=repo_a, check=True)

    diff_result = await extract_diff(project_dir=repo_a)
    patch = diff_result.diff_content
    assert "test.txt" in patch
    (tmp_path / "newfile_diff.patch").write_text(patch)

    repo_b = tmp_path / "repo_b_newfile_diff"
    repo_b.mkdir(parents=True, exist_ok=True)
    (repo_b / "only-in-b.txt").write_text("B\n")
    GitRepository(str(repo_b))
    assert not (repo_b / "test.txt").exists()

    print(patch)
    subprocess.run(
        ["git", "apply", str(tmp_path / "newfile_diff.patch")], cwd=repo_b, check=True
    )
    assert (repo_b / "test.txt").read_text() == "payload\n"


NEW_FILE_ONE_LINE = """\
diff --git a/newfile.txt b/newfile.txt
new file mode 100644
index 0000000..0000000
--- /dev/null
+++ b/newfile.txt
@@ -0,0 +1 @@
+Hello world
"""


def test_tiny_test_diff_ends_with_newline():
    assert NEW_FILE_ONE_LINE.endswith("\n")


@pytest.mark.integration
@pytest.mark.tool
def test_apply_new_file_one_line_patch_should_create_file(tmp_path: Path):
    repo = tmp_path / "repo_manual"
    repo.mkdir(parents=True, exist_ok=True)

    # init git repo with initial commit
    (repo / "base.txt").write_text("base\n")
    GitRepository(str(repo))

    # write patch file
    patch_file = tmp_path / "newfile_one_line.patch"
    text = NEW_FILE_ONE_LINE
    patch_file.write_text(text)

    # apply patch
    subprocess.run(["git", "apply", str(patch_file)], cwd=repo, check=True)

    # verify
    created = repo / "newfile.txt"
    assert created.exists()
    assert created.read_text().strip()


@pytest.mark.integration
@pytest.mark.tool
def test_apply_new_file_after_cli_result_conversion_one_line_patch_should_create_file(
    tmp_path: Path,
):
    repo = tmp_path / "repo_manual"
    repo.mkdir(parents=True, exist_ok=True)

    # init git repo with initial commit
    (repo / "base.txt").write_text("base\n")
    GitRepository(str(repo))

    # write patch file
    patch_file = tmp_path / "newfile_one_line.patch"

    text = (CLIResult(output=NEW_FILE_ONE_LINE)).output
    patch_file.write_text(text)

    # apply patch
    subprocess.run(["git", "apply", str(patch_file)], cwd=repo, check=True)

    # verify
    created = repo / "newfile.txt"
    assert created.exists()
    assert created.read_text().strip()


@pytest.mark.integration
@pytest.mark.tool
def test_apply_new_file_after_diff_entry_conversion_one_line_patch_should_create_file(
    tmp_path: Path,
):
    repo = tmp_path / "repo_manual"
    repo.mkdir(parents=True, exist_ok=True)

    # init git repo with initial commit
    (repo / "base.txt").write_text("base\n")
    GitRepository(str(repo))

    # write patch file
    patch_file = tmp_path / "newfile_one_line.patch"

    text = (DiffEntry(diff_content=NEW_FILE_ONE_LINE)).diff_content
    patch_file.write_text(text)

    # apply patch
    subprocess.run(["git", "apply", str(patch_file)], cwd=repo, check=True)

    # verify
    created = repo / "newfile.txt"
    assert created.exists()
    assert created.read_text().strip()
