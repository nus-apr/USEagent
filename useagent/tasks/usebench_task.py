import subprocess
from pathlib import Path

from usebench.api.datatypes.UnifiedBenchmarkEntry import UnifiedBenchmarkEntry
from usebench.api.utilities.id_management import lookup_uid_from_dataset

from useagent.state.git_repo import GitRepository
from useagent.tasks.task import Task

_DEFAULT_DATASET_PATH: str = "/useagent/data"  # default path in container


class UseBenchTask(Task):
    uid: str
    project_path = "/testbed"  # default path in usebench container

    def __init__(self, uid: str, project_path: str):
        self.uid = uid
        # Initialize the git repository for the project
        self.git_repo = GitRepository(local_path=project_path)
        self.setup_project()

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

        # TODO: this should be added in the benchmark code.
        if "repotest" in self.uid:
            stmt = (
                "I want to add new tests to a new function that was just implemented. Very likely there is no existing tests for this function in the codebase, so I want you to add new tests for it.\n"
                + stmt
            )
        return stmt

    def command_transformer(self, command: str) -> str:
        """
        Transform a plain terminal command into a command that can be run in the container.
        """
        command = (
            command
            if command.startswith("'") and command.endswith("'")
            else "'" + command + "'"
        )
        conda_env_name = "testbed"  # default conda environment in the container
        return f"""conda run -n {conda_env_name} bash -c {command}"""

    def setup_project(self) -> None:
        """
        Run any remaining steps to set up the project.

        Assume we are in a container with both the agent and the target project.
        """
        super().setup_project()
        pytest_install_cmd = "pip install pytest"
        subprocess.run(
            self.command_transformer(pytest_install_cmd),
            shell=True,
            check=True,
            cwd=self.project_path,
        )

    def get_working_directory(self) -> Path:
        return Path(self.project_path)
