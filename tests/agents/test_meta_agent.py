import pytest
from pydantic_ai import capture_run_messages, models
from pydantic_ai.messages import ModelRequest, ModelResponse, UserPromptPart
from pydantic_ai.models.test import TestModel

from useagent.agents.meta.agent import init_agent
from useagent.config import AppConfig
from useagent.pydantic_models.artifacts.git.diff import DiffEntry
from useagent.pydantic_models.output.action import Action
from useagent.pydantic_models.output.answer import Answer
from useagent.pydantic_models.output.code_change import CodeChange
from useagent.pydantic_models.task_state import TaskState
from useagent.state.git_repo import GitRepository
from useagent.tasks.test_task import TestTask

models.ALLOW_MODEL_REQUESTS = False


@pytest.mark.parametrize("output_type", [Answer, Action, CodeChange])
def test_init_meta_agent_can_be_initialized_with_supported_types(output_type):
    test_model = TestModel()
    config = AppConfig(model=test_model)
    config.output_type = output_type

    agent = init_agent(config=config)

    assert len(agent._instructions) >= 1
    # DevNote: Output style instructions are only added at Runtime, not at build time.
    # For the initial instructions there is nothing, but we also don't want to see failures.


@pytest.mark.parametrize("output_type", [DiffEntry, str, int, float])
def test_init_meta_agent_can_be_initialized_with_unsupported_types(output_type):
    test_model = TestModel()
    config = AppConfig(model=test_model)
    config.output_type = output_type

    agent = init_agent(config=config)

    assert len(agent._instructions) >= 1
    # DevNote: Output style instructions are only added at Runtime, not at build time.
    # For the initial instructions there is nothing, but we also don't want to see failures.
    # These types should not give a good instruction later, but for now it's just testing the constructor


@pytest.mark.asyncio
async def test_probing_agent_with_simple_scaffolding_adds_the_required_instructions_for_output_type(
    tmp_path,
):
    """
    DevNote: This is a *very simple* test that just ignores all tool calls and returns an output
    We use it to check that the instructions are actually added.

    More on Pydantic AI Messages and their structure: https://ai.pydantic.dev/api/messages/ (accessed 02.09.2025)
    """
    expected_output = Answer(
        answer="I like football",
        explanation="It's just so fun, you can hang out with 10 friends and 11 enemies.",
        doubts="Maybe this is a media constructed fascination and I should reflect on my consumption habits and effects of advertisement.",
        environment=None,
    )

    test_model = TestModel(call_tools=[], custom_output_args=expected_output)
    task = TestTask(root=str(tmp_path))
    state = TaskState(
        task=task,
        # Note Issue#1: I had `.` here and it replaced my git user name in the repository level upon running tests.
        git_repo=GitRepository(local_path=tmp_path),
    )

    config = AppConfig(model=test_model, output_type=Answer)
    agent = init_agent(config=config, output_type=Answer)

    print(state._task, type(state._task))
    with capture_run_messages() as history:
        _ = await agent.run("Test Test", deps=state)

    seen_output: bool = False
    seen_doubt: bool = False
    seen_answer: bool = False
    for message in history:
        if isinstance(message, ModelRequest) and isinstance(
            message.parts[0], UserPromptPart
        ):
            request: ModelRequest = message
            seen_output |= "output:" in request.instructions.lower()
            seen_doubt |= "doubt" in request.instructions.lower()
        if isinstance(message, ModelResponse):
            seen_answer = True

    assert seen_output
    assert seen_doubt
    assert seen_answer
