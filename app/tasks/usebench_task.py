from dataclasses import dataclass

from usebench.api import runner as usebench_runner
from usebench.api.datatypes.UnifiedBenchmarkEntry import UnifiedBenchmarkEntry
from usebench.api.utilities.id_management import lookup_uid_from_dataset

from docker.models.containers import Container

from subprocess import DEVNULL, CalledProcessError

from utils import cd, run_command


class GitRepository:
    """
    Encapsulates everything related to a code respository (must be git).
    """

    local_path: str

    def __init__(self, local_path: str):
        self.local_path = local_path
        self._configure_git()

    def _configure_git(self) -> None:
        """
        Configure git user name and email for the repository.
        This is necessary for committing changes.
        """
        run_command(["git", "config", "--global", "user.name", "USEagent"])
        run_command(
            ["git", "config", "--global", "user.email", "useagent@useagent.com"]
        )

    def repo_clean_changes(self) -> None:
        """
        Reset repo to HEAD. Basically clean active changes and untracked files on top of HEAD.
        """
        with cd(self.local_path):
            reset_cmd = ["git", "reset", "--hard"]
            clean_cmd = ["git", "clean", "-fd"]
            run_command(reset_cmd, stdout=DEVNULL, stderr=DEVNULL)
            run_command(clean_cmd, stdout=DEVNULL, stderr=DEVNULL)


_DEFAULT_DATASET_PATH: str = (
    "./use-bench/data"  # This is the 'default' dataset location when coming from the README
)


class UseBenchTask:
    uid: str
    # a local git repository that is a bind mount to the source code dir in the container.
    git_repo: GitRepository
    # A container containing the subject environment.
    # The agent is responsible for managing the states inside the container.
    container: Container | None = None

    def __init__(self, uid: str, project_path: str):
        self.uid = uid
        # Initialize the git repository for the project
        self.git_repo = GitRepository(local_path=project_path)

    def execute_command(
        self, command: str, timeout: int | None = None
    ) -> tuple[int, str, str]:

        if timeout is None:
            command_exec_res = usebench_runner.run_command(
                uid=self.uid,
                command=command,
                dataset_path_or_name=_DEFAULT_DATASET_PATH,
            )
        else:
            command_exec_res = usebench_runner.run_command(
                uid=self.uid,
                command=command,
                dataset_path_or_name=_DEFAULT_DATASET_PATH,
                timeout_in_seconds=timeout,
            )

        if command_exec_res is None:
            # logger.info(f"Command execution failed for {command}")
            return -1, "", ""

        # logger.debug(f"[USEBenchTask] execute_command: res is {command_exec_res}")
        # logger.debug(f"[USEBenchTask] res output is {command_exec_res.output}")

        rc = command_exec_res.exit_code
        output = command_exec_res.output.decode(errors="ignore")

        # TODO: separate the two streams from usebench_runner.run_command
        return rc, output, ""

    def reset_project(self):
        self.git_repo.repo_clean_changes()

    def _lookup_benchmark_entry(self) -> UnifiedBenchmarkEntry:
        """
        Backlinks from this task uid to the full BenchmarkEntry.

        There should never be a case where this effectively returns None.
        In theory there can be valid uids which might not be in the current split or reduced form of the dataset.
        But then we just live with the crash for now, as something very wrong must be happening if there are
        tasks in input that are not in the correct dataset.
        """
        unified_entry = lookup_uid_from_dataset(
            self.uid, dataset_path_or_name=_DEFAULT_DATASET_PATH
        )
        if unified_entry is None:
            raise ValueError(f"Could not find entry for {self.uid}")
        return unified_entry


    def get_issue_statement(self) -> str:
        entry = self._lookup_benchmark_entry()
        stmt = entry.full_task_statement

        if "repotest" in self.uid:
            stmt = (
                "I want to add new tests to a new function that was just implemented. Very likely there is no existing tests for this function in the codebase, so I want you to add new tests for it.\n"
                + stmt
            )
        return stmt