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
