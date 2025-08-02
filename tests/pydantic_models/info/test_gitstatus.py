import pytest
from pydantic import ValidationError

from useagent.pydantic_models.info.environment import GitStatus


@pytest.mark.pydantic_model
@pytest.mark.parametrize(
    "commit", ["abc1234", " abc1234 ", "\tabc1234\n", "0123456789abcdef"]
)
@pytest.mark.parametrize("branch", ["main", " main ", "\tmain\n", "feature/new"])
def test_valid_git_status(commit: str, branch: str):
    GitStatus(
        active_git_commit=commit,
        active_git_commit_is_head=True,
        active_git_branch=branch,
        has_uncommited_changes=False,
    )


@pytest.mark.pydantic_model
@pytest.mark.parametrize(
    "commit", ["", " ", "\n", "abc12", "ZZZZZZZ", "123@abc", "abc..123"]
)
def test_invalid_git_commit(commit: str):
    with pytest.raises(ValidationError):
        GitStatus(
            active_git_commit=commit,
            active_git_commit_is_head=False,
            active_git_branch="main",
            has_uncommited_changes=True,
        )


@pytest.mark.pydantic_model
@pytest.mark.parametrize(
    "branch",
    ["", " ", "\t", "main..fix", "/start", "end/", "bad//branch", "@", "fix.lock"],
)
def test_invalid_git_branch(branch: str):
    with pytest.raises(ValidationError):
        GitStatus(
            active_git_commit="abc1234",
            active_git_commit_is_head=False,
            active_git_branch=branch,
            has_uncommited_changes=True,
        )


@pytest.mark.pydantic_model
def test_get_output_instructions_should_not_return_none():
    assert GitStatus.get_output_instructions()
