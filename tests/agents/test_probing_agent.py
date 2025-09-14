from pathlib import Path

import pytest
from pydantic_ai import capture_run_messages, models
from pydantic_ai.messages import ModelRequest, ModelResponse, UserPromptPart
from pydantic_ai.models.test import TestModel

from useagent.agents.probing.agent import init_agent
from useagent.config import AppConfig
from useagent.pydantic_models.artifacts.git.diff import DiffEntry
from useagent.pydantic_models.info.environment import GitStatus, Package

models.ALLOW_MODEL_REQUESTS = False


@pytest.mark.agent
@pytest.mark.parametrize("output_type", [GitStatus, list[Package], Path])
def test_init_edit_agent_can_be_initialized_with_supported_types(output_type):
    test_model = TestModel()
    config = AppConfig(model=test_model)

    agent = init_agent(output_type, config=config)

    assert len(agent._instructions) >= 1
    # DevNote: Output style instructions are only added at Runtime, not at build time.
    # For the initial instructions there is nothing, but we also don't want to see failures.


@pytest.mark.agent
@pytest.mark.parametrize("output_type", [DiffEntry, str, int, float])
def test_init_edit_agent_can_be_initialized_with_unsupported_types(output_type):
    test_model = TestModel()
    config = AppConfig(model=test_model)

    agent = init_agent(output_type, config=config)

    assert len(agent._instructions) >= 1
    # DevNote: Output style instructions are only added at Runtime, not at build time.
    # For the initial instructions there is nothing, but we also don't want to see failures.
    # These types should not give a good instruction later, but for now it's just testing the constructor


@pytest.mark.agent
@pytest.mark.asyncio
async def test_probing_agent_with_simple_scaffolding_adds_the_required_instructions_for_output_type(
    tmp_path,
):
    """
    DevNote: This is a *very simple* test that just ignores all tool calls and returns an output
    We use it to check that the instructions are actually added.

    More on Pydantic AI Messages and their structure: https://ai.pydantic.dev/api/messages/ (accessed 02.09.2025)
    """
    expected_output = GitStatus(
        active_git_commit="abc1234",
        active_git_commit_is_head=True,
        active_git_branch="main",
        has_uncommited_changes=False,
    )

    test_model = TestModel(call_tools=[], custom_output_args=expected_output)
    config = AppConfig(model=test_model)

    agent = init_agent(GitStatus, config=config)

    with capture_run_messages() as history:
        _ = await agent.run("Test Test", deps=None)

    seen_output: bool = False
    seen_gitstatus: bool = False
    seen_answer: bool = False
    for message in history:
        if isinstance(message, ModelRequest) and isinstance(
            message.parts[0], UserPromptPart
        ):
            request: ModelRequest = message
            seen_output |= "output:" in request.instructions.lower()
            seen_gitstatus |= "gitstatus" in request.instructions.lower()
        if isinstance(message, ModelResponse):
            seen_answer = True

    assert seen_output
    assert seen_gitstatus
    assert seen_answer
