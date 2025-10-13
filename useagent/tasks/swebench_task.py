import json
import re
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from datasets import load_dataset
from loguru import logger

from useagent.state.git_repo import GitRepository
from useagent.tasks.task import Task

_default_working_dir = Path("/tmp/working_dir")


class SWEbenchTask(Task):
    """
    Task for materializing a SWE-bench (Verified) instance into a working directory.
    Uses the HF dataset metadata to get repo, base_commit, and a task description.
    """

    instance_id: str
    repo: str
    base_commit: str
    issue_statement: str
    uid: str
    _working_dir: Path
    _default_branch_name: str = "useagent"

    def __init__(
        self,
        instance_id: str,
        working_dir: Path = _default_working_dir,
        dataset: str = "princeton-nlp/SWE-bench_Verified",
        split: str = "test",
    ):
        if not instance_id or not instance_id.strip():
            raise ValueError("instance_id must be a non-empty string")
        instance_id = instance_id.strip()

        if not working_dir:
            raise ValueError("working_dir must be a valid Path instance")

        self._assert_instance_exists(
            instance_id, dataset, (split, "validation", "train", "test")
        )

        meta = self._load_instance_meta(instance_id, dataset, split)
        repo: str = meta["repo"]
        base_commit: str = meta["base_commit"]
        issue_statement: str = meta["issue_statement"]

        if not re.fullmatch(r"[0-9a-fA-F]{7,40}", base_commit):
            raise ValueError(
                "base_commit must be a valid git SHA (7-40 hex characters)"
            )

        self.instance_id = instance_id
        self.repo = repo
        self.base_commit = base_commit
        self.issue_statement = issue_statement
        self.uid = instance_id
        self._working_dir = working_dir

        logger.info(
            f"[Setup] SWE-bench {instance_id}: cloning {self.repo}@{self.base_commit} into {working_dir}"
        )

        self._materialize_repo()
        self.git_repo = GitRepository(local_path=str(self._working_dir))
        self.setup_project()
        logger.info(f"[Setup] Finished setting up {instance_id} into {working_dir}")

    def get_issue_statement(self) -> str:
        return self.issue_statement

    def get_working_directory(self) -> Path:
        return self._working_dir

    @classmethod
    def get_default_working_dir(cls) -> Path:
        return _default_working_dir

    # --- internals ---

    @staticmethod
    def _hf_row_to_meta(row: dict[str, Any]) -> dict[str, str]:
        repo = row.get("repo") or row.get("repo_name") or row.get("repository") or ""
        base_commit = row.get("base_commit") or row.get("commit") or ""
        issue_statement = (
            row.get("problem_statement")
            or row.get("title")
            or row.get("summary")
            or f"SWE-bench task {row.get('instance_id','')}"
        )
        if not repo:
            raise ValueError("Dataset row missing repo")
        if not base_commit:
            raise ValueError("Dataset row missing base_commit")
        return {
            "repo": repo,
            "base_commit": base_commit,
            "issue_statement": issue_statement,
        }

    @staticmethod
    def _normalize_repo_url(repo: str) -> str:
        if repo.startswith(("http://", "https://", "git@")):
            url = repo
        else:
            url = f"https://github.com/{repo}"
        if not url.endswith(".git"):
            url += ".git"
        return url

    def _load_instance_meta(
        self, instance_id: str, dataset: str, split: str
    ) -> dict[str, str]:
        ds = load_dataset(dataset, split=split)
        row = next((r for r in ds if r.get("instance_id") == instance_id), None)  # type: ignore
        if row is None:
            # fallback: try other common splits
            for s in ("train", "validation"):
                try:
                    ds2 = load_dataset(dataset, split=s)
                    row = next(
                        (r for r in ds2 if r.get("instance_id") == instance_id), None  # type: ignore
                    )
                    if row:
                        break
                except Exception:
                    pass
        if row is None:
            raise ValueError(
                f"[Setup] Instance {instance_id} not found in {dataset}/{split}"
            )
        return self._hf_row_to_meta(row)  # type: ignore[arg-type]

    def _materialize_repo(self) -> None:
        if self._working_dir.exists():
            for p in self._working_dir.iterdir():
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
        else:
            self._working_dir.mkdir(parents=True, exist_ok=True)

        repo_url = self._normalize_repo_url(self.repo)

        # Initialize an empty repo, fetch ONLY the target commit (and its ancestors),
        # create a local branch at that commit. No remote branches are fetched,
        # so no newer commits are present.
        subprocess.run(["git", "init", str(self._working_dir)], check=True)
        subprocess.run(
            ["git", "-C", str(self._working_dir), "remote", "add", "origin", repo_url],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self._working_dir),
                "fetch",
                "--no-tags",
                "--prune",
                "origin",
                self.base_commit,
            ],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self._working_dir),
                "checkout",
                "-B",
                self._default_branch_name,
                self.base_commit,
            ],
            check=True,
        )
        # Ensure the branch is local-only (no upstream), avoiding accidental pulls of newer commits.
        subprocess.run(
            [
                "git",
                "-C",
                str(self._working_dir),
                "config",
                f"branch.{self._default_branch_name}.remote",
            ],
            check=False,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self._working_dir),
                "config",
                "--unset",
                f"branch.{self._default_branch_name}.remote",
            ],
            check=False,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self._working_dir),
                "config",
                "--unset",
                f"branch.{self._default_branch_name}.merge",
            ],
            check=False,
        )

    @staticmethod
    def _assert_instance_exists(
        instance_id: str, dataset: str, splits: Iterable[str]
    ) -> None:
        if not instance_id or not instance_id.strip():
            logger.error("[Setup] Empty instance_id provided for dataset {}", dataset)
            raise ValueError("instance_id must be a non-empty string")
        instance_id = instance_id.strip()
        seen: set[str] = set()
        for s in splits:
            if s in seen:
                continue
            seen.add(s)
            try:
                ds = load_dataset(dataset, split=s)
            except Exception:
                continue
            if any(r.get("instance_id") == instance_id for r in ds):  # type: ignore
                return
        logger.error(
            "[Setup] Instance {} not found in dataset {} (splits tried: {})",
            instance_id,
            dataset,
            ", ".join(seen),
        )
        raise ValueError(f"Instance {instance_id} not found in {dataset}")

    def postprocess_swebench_task(self, result: str | None, output_dir: Path) -> None:
        """
        Writes the given task to a nearby file, matching the swe-bench format.
        The result is meant to be a diff, the resolved diff_entry.diff_id, without any encoding applied yet.
        """
        instance_id: str = self.instance_id
        model_patch: str = result if result is not None else ""

        if model_patch and model_patch.strip():
            logger.info(
                f"[Task] Postprocessing SWEbench Task {instance_id}, storing a Patch with {len(model_patch)} LoC to {output_dir}/{instance_id}.json"
            )
        else:
            logger.warning(
                f"[Task] Proprocessing SWEBench Task {instance_id} received an empty result - storing a empty result to {output_dir}/{instance_id}.json"
            )

        entry: dict[str, Any] = {"model_patch": model_patch}
        entry["model_name_or_path"] = "useagent-turbo-dev"

        predictions: dict[str, Any] = {instance_id: entry}

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path: Path = output_dir / f"{instance_id}.json"

        # UTF-8, no BOM; normalize to '\n' to avoid platform-dependent newlines in the JSON file.
        with out_path.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(predictions, f, ensure_ascii=False)
        logger.debug(f"[Task] finished writing SWEbench-Task {instance_id}")
