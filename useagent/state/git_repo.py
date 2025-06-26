from subprocess import DEVNULL, CalledProcessError

from useagent.utils import cd, run_command
import os

from loguru import logger

class GitRepository:
    """
    Encapsulates everything related to a code respository (must be git).
    """

    local_path: str

    def __init__(self, local_path: str):
        logger.info(f"Setting up a Git Repository at {local_path}")
        self.local_path = local_path
        with cd(self.local_path):
            self._configure_git()
            self.initialize_git_if_needed()

    def _configure_git(self) -> None:
        """
        Configure git user name and email for the repository.
        This is necessary for committing changes.
        """
        logger.debug(f"Configuring git user and email")
        run_command(["git", "config", "user.name", "USEagent"])
        run_command(["git", "config", "user.email", "useagent@useagent.com"])


    def initialize_git_if_needed(self) -> None:
        # DevNote:
        # Given Local issues, there might not yet be a git repository.
        # But we need also to introduce a .git repository AND make the first commit, otherwise the later diff-extractor is very confused.
        if not os.path.isdir(os.path.join(self.local_path, ".git")):
            run_command(["git", "init", "--quiet"])
            self._configure_git()
            run_command(["git", "add", "."])
            run_command(["git", "commit", "-m", "Initial commit"], stdout=DEVNULL, stderr=DEVNULL)
            logger.info(f"{self.local_path} was NOT a git repository - initialized a repository and made an initial commit.")

    def repo_clean_changes(self) -> None:
        """
        Reset repo to HEAD. Basically clean active changes and untracked files on top of HEAD.
        """
        with cd(self.local_path):
            logger.debug(f"Resetting git repository at {self.local_path}")

            reset_cmd = ["git", "reset", "--hard"]
            clean_cmd = ["git", "clean", "-fd"]
            run_command(reset_cmd, stdout=DEVNULL, stderr=DEVNULL)
            run_command(clean_cmd, stdout=DEVNULL, stderr=DEVNULL)
