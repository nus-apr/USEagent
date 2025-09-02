import pytest
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from useagent.agents.search_code.agent import init_agent
from useagent.config import AppConfig

models.ALLOW_MODEL_REQUESTS = False


@pytest.mark.agent
def test_init_search_agent_can_be_initialized():
    test_model = TestModel()
    config = AppConfig(model=test_model)

    agent = init_agent(config=config)

    assert len(agent._instructions) >= 1
    # DevNote: Output style instructions are only added at Runtime, not at build time.
    # For the initial instructions there is nothing, but we also don't want to see failures.
