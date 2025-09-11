import json
import shutil
import subprocess
from pathlib import Path

import pytest

from useagent.tasks.swebench_task import SWEbenchTask

DATASET = "princeton-nlp/SWE-bench_Verified"
SPLITS = ("test", "validation", "train")
KNOWN_IDS = [
    "astropy__astropy-12907",
    "sphinx-doc__sphinx-8265",
    "django__django-15695",
    "django__django-16100",
    "matplotlib__matplotlib-24026",
]


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, check=False, capture_output=True)


def test__hf_row_to_meta_should_extract_fields() -> None:
    row = {
        "repo": "psf/requests",
        "base_commit": "a" * 40,
        "problem_statement": "Fix bug",
        "instance_id": "psf__requests-0000",
    }
    m = SWEbenchTask._hf_row_to_meta(row)
    assert m["repo"] == "psf/requests"
    assert m["base_commit"] == "a" * 40
    assert m["issue_statement"] == "Fix bug"


@pytest.mark.parametrize(
    "row",
    [
        {"base_commit": "a" * 40, "problem_statement": "x"},
        {"repo": "psf/requests", "problem_statement": "x"},
    ],
)
def test__hf_row_to_meta_should_raise_on_missing_fields(row: dict) -> None:
    with pytest.raises(ValueError):
        SWEbenchTask._hf_row_to_meta(row)


@pytest.mark.parametrize(
    "inp,expected",
    [
        ("owner/repo", "https://github.com/owner/repo.git"),
        ("https://github.com/owner/repo", "https://github.com/owner/repo.git"),
        ("https://github.com/owner/repo.git", "https://github.com/owner/repo.git"),
        ("git@github.com:owner/repo.git", "git@github.com:owner/repo.git"),
    ],
)
def test__normalize_repo_url_should_return_https_or_keep_git(
    inp: str, expected: str
) -> None:
    assert SWEbenchTask._normalize_repo_url(inp) == expected


@pytest.mark.parametrize("bad", [None, "", " ", "\n", "\t"])
def test_invalid_instance_id_should_raise(bad: str | None, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        SWEbenchTask(instance_id=bad, working_dir=tmp_path / "wd")  # type: ignore[arg-type]


def test_invalid_working_dir_should_raise(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        SWEbenchTask(instance_id="astropy__astropy-12907", working_dir=None)  # type: ignore[arg-type]


@pytest.mark.online
@pytest.mark.slow
@pytest.mark.parametrize(
    "instance_id",
    [
        "astropy__astropy-12907",
        "sphinx-doc__sphinx-8265",
        "django__django-15695",
        "django__django-16100",
    ],
)
def test_materialize_should_checkout_base_commit_and_branch(
    tmp_path: Path, instance_id: str
) -> None:
    dest = tmp_path / f"wb_{instance_id}"
    task = SWEbenchTask(instance_id=instance_id, working_dir=dest)

    head = _git(dest, "rev-parse", "HEAD").stdout.decode().strip()
    assert head and len(head) == 40
    assert head == task.base_commit

    branch = _git(dest, "branch", "--show-current").stdout.decode().strip()
    assert branch == "useagent"

    res = _git(dest, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    assert res.returncode != 0

    remotes = (
        _git(dest, "for-each-ref", "refs/remotes", "--format=%(refname)")
        .stdout.decode()
        .strip()
    )
    assert remotes == ""

    descendants = (
        _git(dest, "rev-list", "--ancestry-path", "HEAD..", "--all")
        .stdout.decode()
        .strip()
    )
    assert descendants == ""


@pytest.mark.online
@pytest.mark.slow
@pytest.mark.parametrize(
    "instance_id", ["astropy__astropy-12907", "sphinx-doc__sphinx-8265"]
)
def test_overwrite_existing_dir_should_clean_and_clone(
    tmp_path: Path, instance_id: str
) -> None:
    dest = tmp_path / f"overwrite_{instance_id}"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "old.txt").write_text("old")

    SWEbenchTask(instance_id=instance_id, working_dir=dest)

    assert not (dest / "old.txt").exists()
    assert (dest / ".git").exists()


@pytest.mark.online
@pytest.mark.slow
def test_get_working_directory_should_return_path(tmp_path: Path) -> None:
    dest = tmp_path / "wd_ret"
    task = SWEbenchTask(instance_id="astropy__astropy-12907", working_dir=dest)
    assert task.get_working_directory() == dest


@pytest.mark.online
@pytest.mark.slow
def test_uid_should_equal_instance_id(tmp_path: Path) -> None:
    inst = "sphinx-doc__sphinx-8265"
    task = SWEbenchTask(instance_id=inst, working_dir=tmp_path / "uid")
    assert task.uid == inst


@pytest.mark.online
@pytest.mark.parametrize(
    "raw",
    [
        "astropy__astropy-12907",
        " astropy__astropy-12907",
        "astropy__astropy-12907 ",
        "\nastropy__astropy-12907\t",
        " \t\nastropy__astropy-12907 \n\t",
    ],
)
def test_assert_instance_exists_should_accept_valid_ids_with_whitespace(
    raw: str,
) -> None:
    SWEbenchTask._assert_instance_exists(raw, DATASET, SPLITS)


@pytest.mark.online
@pytest.mark.parametrize("bad", ["", " ", "\n", "\t", " \n\t "])
def test_assert_instance_exists_should_raise_for_empty_or_whitespace_only(
    bad: str,
) -> None:
    with pytest.raises(ValueError):
        SWEbenchTask._assert_instance_exists(bad, DATASET, SPLITS)


@pytest.mark.slow
@pytest.mark.online
@pytest.mark.parametrize("unknown", ["unknown__repo-99999", "definitely__not-00000"])
def test_assert_instance_exists_should_raise_for_unknown_ids(unknown: str) -> None:
    with pytest.raises(ValueError):
        SWEbenchTask._assert_instance_exists(unknown, DATASET, SPLITS)


@pytest.mark.online
@pytest.mark.parametrize("iid", KNOWN_IDS)
def test_assert_instance_exists_should_pass_for_known_ids(iid: str) -> None:
    SWEbenchTask._assert_instance_exists(iid, DATASET, SPLITS)


@pytest.mark.online
@pytest.mark.slow
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("sphinx-doc__sphinx-8265", "sphinx-doc__sphinx-8265"),
        (" sphinx-doc__sphinx-8265", "sphinx-doc__sphinx-8265"),
        ("\nsphinx-doc__sphinx-8265\t", "sphinx-doc__sphinx-8265"),
    ],
)
def test_constructor_should_strip_instance_id_and_set_attribute(
    tmp_path: Path, raw: str, expected: str
) -> None:
    task = SWEbenchTask(instance_id=raw, working_dir=tmp_path / "wb_trim")
    assert task.instance_id == expected


@pytest.mark.slow
@pytest.mark.online
@pytest.mark.parametrize("iid", KNOWN_IDS)
def test_load_instance_meta_should_return_nonempty_issue_statement(iid: str) -> None:
    t = SWEbenchTask.__new__(SWEbenchTask)
    meta = t._load_instance_meta(iid, DATASET, "test")
    assert isinstance(meta["issue_statement"], str)
    assert meta["issue_statement"].strip() != ""


@pytest.mark.online
@pytest.mark.slow
@pytest.mark.parametrize("iid", ["sphinx-doc__sphinx-8265", "django__django-16100"])
def test_constructor_should_set_nonempty_issue_statement(
    tmp_path: Path, iid: str
) -> None:
    task = SWEbenchTask(instance_id=iid, working_dir=tmp_path / f"wb_{iid}")
    assert isinstance(task.issue_statement, str)
    assert task.issue_statement.strip() != ""


@pytest.mark.online
@pytest.mark.slow
def test_default_working_dir_should_contain_files_after_setup() -> None:
    wd = SWEbenchTask.get_default_working_dir()
    if wd.exists():
        shutil.rmtree(wd)
    SWEbenchTask(instance_id="sphinx-doc__sphinx-8265")
    assert any(wd.iterdir())


@pytest.mark.online
@pytest.mark.slow
@pytest.mark.parametrize("iid", ["sphinx-doc__sphinx-8265", "django__django-16100"])
def test_get_issue_statement_should_return_nonempty_string(
    tmp_path: Path, iid: str
) -> None:
    task = SWEbenchTask(
        instance_id=iid, working_dir=tmp_path / f"wb_{iid}", dataset=DATASET
    )
    s = task.get_issue_statement()
    assert isinstance(s, str)
    assert s.strip() != ""


@pytest.mark.online
@pytest.mark.slow
@pytest.mark.parametrize("iid", ["sphinx-doc__sphinx-8265"])
def test_get_issue_statement_should_match_dataset_meta(
    tmp_path: Path, iid: str
) -> None:
    task = SWEbenchTask(
        instance_id=iid, working_dir=tmp_path / "wb_meta", dataset=DATASET
    )
    meta = task._load_instance_meta(iid, DATASET, "test")
    assert task.get_issue_statement().strip() == meta["issue_statement"].strip()


@pytest.mark.online
@pytest.mark.slow
@pytest.mark.parametrize(
    "raw,expected",
    [
        (" sphinx-doc__sphinx-8265", "sphinx-doc__sphinx-8265"),
        ("\nsphinx-doc__sphinx-8265\t", "sphinx-doc__sphinx-8265"),
    ],
)
def test_get_issue_statement_should_work_with_whitespace_ids(
    tmp_path: Path, raw: str, expected: str
) -> None:
    task = SWEbenchTask(
        instance_id=raw, working_dir=tmp_path / "wb_ws", dataset=DATASET
    )
    assert task.instance_id == expected
    assert task.get_issue_statement().strip() != ""


@pytest.mark.online
@pytest.mark.slow
@pytest.mark.parametrize("iid", ["sphinx-doc__sphinx-8265", "django__django-16100"])
def test_materialize_should_have_no_tags(tmp_path: Path, iid: str) -> None:
    dest = tmp_path / f"wb_notags_{iid}"
    SWEbenchTask(instance_id=iid, working_dir=dest)
    tags = _git(dest, "tag", "--list").stdout.decode().strip()
    assert tags == ""


@pytest.mark.online
@pytest.mark.slow
@pytest.mark.parametrize("iid", ["sphinx-doc__sphinx-8265", "django__django-16100"])
def test_useagent_branch_should_have_no_upstream_config(
    tmp_path: Path, iid: str
) -> None:
    dest = tmp_path / f"wb_noupstream_{iid}"
    SWEbenchTask(instance_id=iid, working_dir=dest)
    remote = _git(dest, "config", "--get", "branch.useagent.remote")
    merge = _git(dest, "config", "--get", "branch.useagent.merge")
    assert remote.returncode != 0
    assert merge.returncode != 0


@pytest.mark.online
@pytest.mark.slow
@pytest.mark.parametrize("iid", ["sphinx-doc__sphinx-8265", "django__django-16100"])
def test_short_commit_prefix_should_resolve_to_head(tmp_path: Path, iid: str) -> None:
    dest = tmp_path / f"wb_short_{iid}"
    task = SWEbenchTask(instance_id=iid, working_dir=dest)
    short = task.base_commit[:7]
    resolved = _git(dest, "rev-parse", "--verify", short).stdout.decode().strip()
    head = _git(dest, "rev-parse", "HEAD").stdout.decode().strip()
    assert resolved == head


@pytest.mark.online
@pytest.mark.slow
def test_postprocess_should_write_file_with_patch(tmp_path: Path) -> None:
    task = SWEbenchTask(
        instance_id="sphinx-doc__sphinx-8265",
        working_dir=tmp_path / "wd",
        dataset=DATASET,
    )
    outdir = tmp_path / "preds"
    diff = "--- a/file.py\n+++ b/file.py\n+print('hello')\n"

    task.postprocess_swebench_task(result=diff, output_dir=outdir)

    out_path = outdir / f"{task.instance_id}.json"
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data[task.instance_id]["model_patch"] == diff


@pytest.mark.online
@pytest.mark.slow
def test_postprocess_none_should_write_empty_patch(tmp_path: Path) -> None:
    task = SWEbenchTask(
        instance_id="sphinx-doc__sphinx-8265",
        working_dir=tmp_path / "wd2",
        dataset=DATASET,
    )
    outdir = tmp_path / "preds2"

    task.postprocess_swebench_task(result=None, output_dir=outdir)

    data = json.loads((outdir / f"{task.instance_id}.json").read_text(encoding="utf-8"))
    assert data[task.instance_id]["model_patch"] == ""


@pytest.mark.online
@pytest.mark.slow
def test_postprocess_should_preserve_unicode_and_newlines(tmp_path: Path) -> None:
    task = SWEbenchTask(
        instance_id="sphinx-doc__sphinx-8265",
        working_dir=tmp_path / "wd3",
        dataset=DATASET,
    )
    diff = "diff --git a/ä.py b/漢.py\r\n+print('mañana')\n"

    task.postprocess_swebench_task(result=diff, output_dir=tmp_path)

    data = json.loads(
        (tmp_path / f"{task.instance_id}.json").read_text(encoding="utf-8")
    )
    assert data[task.instance_id]["model_patch"] == diff


@pytest.mark.online
@pytest.mark.slow
def test_postprocess_output_file_should_be_utf8(tmp_path: Path) -> None:
    task = SWEbenchTask(
        instance_id="sphinx-doc__sphinx-8265",
        working_dir=tmp_path / "wd4",
        dataset=DATASET,
    )
    diff = "á\nβ\n漢\n"

    task.postprocess_swebench_task(result=diff, output_dir=tmp_path)

    txt = (tmp_path / f"{task.instance_id}.json").read_text(encoding="utf-8")
    data = json.loads(txt)
    assert data[task.instance_id]["model_patch"] == diff


@pytest.mark.online
@pytest.mark.slow
@pytest.mark.parametrize("iid", ["sphinx-doc__sphinx-8265", "django__django-15695"])
def test_postprocess_should_write_issue_and_gold_with_fake_result(
    tmp_path: Path, iid: str
) -> None:
    task = SWEbenchTask(
        instance_id=iid,
        working_dir=tmp_path / f"wd_{iid}_fake",
        dataset=DATASET,
    )
    outdir = tmp_path / f"preds_{iid}_fake"
    fake_diff = "--- a/x.py\n+++ b/x.py\n+print('fake')\n"

    task.postprocess_swebench_task(result=fake_diff, output_dir=outdir)

    # JSON still produced
    json_path = outdir / f"{task.instance_id}.json"
    assert json_path.exists()

    # New files: original_issue.txt and gold_patch.diff
    issue_path = outdir / "original_issue.txt"
    gold_path = outdir / "gold_patch.diff"

    assert issue_path.exists()
    assert gold_path.exists()

    issue_txt = issue_path.read_text(encoding="utf-8")
    gold_txt = gold_path.read_text(encoding="utf-8")

    assert isinstance(issue_txt, str) and issue_txt.strip() != ""
    assert isinstance(gold_txt, str) and gold_txt.strip() != ""


@pytest.mark.online
@pytest.mark.slow
@pytest.mark.parametrize("iid", ["sphinx-doc__sphinx-8265", "django__django-15695"])
def test_postprocess_should_write_issue_and_gold_with_empty_result(
    tmp_path: Path, iid: str
) -> None:
    task = SWEbenchTask(
        instance_id=iid,
        working_dir=tmp_path / f"wd_{iid}_empty",
        dataset=DATASET,
    )
    outdir = tmp_path / f"preds_{iid}_empty"

    task.postprocess_swebench_task(result=None, output_dir=outdir)

    # JSON with empty patch
    data = json.loads((outdir / f"{task.instance_id}.json").read_text(encoding="utf-8"))
    assert data[task.instance_id]["model_patch"] == ""

    # New files still produced and match attributes
    issue_path = outdir / "original_issue.txt"
    gold_path = outdir / "gold_patch.diff"

    assert issue_path.exists()
    assert gold_path.exists()
