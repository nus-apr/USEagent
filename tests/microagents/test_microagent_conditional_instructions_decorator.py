import pytest
from typing import List

from useagent.microagents.management import alias_for_microagents, conditional_microagents_triggers
from useagent.microagents.microagent import MicroAgent
from useagent.config import AppConfig

from pydantic_ai import models, capture_run_messages
from pydantic_ai.agent import Agent
from pydantic_ai.models.test import TestModel
from pydantic_ai.messages import ModelRequest

models.ALLOW_MODEL_REQUESTS = False


@pytest.fixture
def test_model() -> TestModel:
    return TestModel(call_tools=[], custom_output_text="ok")


@pytest.fixture
def config(test_model: TestModel) -> AppConfig:
    return AppConfig(model=test_model)


@pytest.mark.agent
@pytest.mark.asyncio
async def test_conditional_microagents_trigger_matching_keyword(config):
    microagents = [
        MicroAgent("test_microagent", "1.0.0", ["MY_AGENT"], ["trigger_a"], "foo")
    ]

    @conditional_microagents_triggers(microagents)
    @alias_for_microagents("MY_AGENT")
    def init_agent(config: AppConfig) -> Agent:
        return Agent(model=config.model, output_type=str)

    agent = init_agent(config)

    with capture_run_messages() as history:
        await agent.run("Do something with trigger_a")

    assert any(
        isinstance(m, ModelRequest) and m.instructions and "foo" in m.instructions
        for m in history
    )


@pytest.mark.agent
@pytest.mark.asyncio
async def test_conditional_microagents_trigger_matching_keyword_when_agent_id_is_given_per_field(config):
    microagents = [
        MicroAgent("test_microagent", "1.0.0", ["MY_AGENT"], ["trigger_a"], "foo")
    ]

    @conditional_microagents_triggers(microagents)
    def init_agent(config: AppConfig) -> Agent:
        agent = Agent(model=config.model, output_type=str)
        agent.agent_id = "MY_AGENT"
        return agent

    agent = init_agent(config)

    with capture_run_messages() as history:
        await agent.run("Do something with trigger_a")

    assert any(
        isinstance(m, ModelRequest) and m.instructions and "foo" in m.instructions
        for m in history
    )


@pytest.mark.agent
@pytest.mark.asyncio
async def test_conditional_microagents_wrong_order_of_alias_and_microagent_decorator_raises_error(test_model):
    microagents = [
        MicroAgent("test_microagent", "1.0.0", ["MY_AGENT"], ["trigger_a"], "triggered")
    ]

    with pytest.raises(ValueError):
        @alias_for_microagents("MY_AGENT")
        @conditional_microagents_triggers(microagents)
        def init_agent(config: AppConfig) -> Agent:
            return Agent(model=config.model, output_type=str)

        init_agent(AppConfig(model=test_model))


@pytest.mark.agent
@pytest.mark.asyncio
async def test_conditional_microagents_no_alias_given_raises_error(test_model):
    microagents = [
        MicroAgent("test_microagent", "1.0.0", ["MY_AGENT"], ["trigger_a"], "triggered")
    ]

    with pytest.raises(ValueError):
        @conditional_microagents_triggers(microagents)
        def init_agent(config: AppConfig) -> Agent:
            return Agent(model=test_model, output_type=str)

        init_agent(AppConfig(model=test_model))


@pytest.mark.agent
@pytest.mark.asyncio
async def test_conditional_microagents_empty_list_does_nothing(config):
    @conditional_microagents_triggers([])
    @alias_for_microagents("MY_AGENT")
    def init_agent(config: AppConfig) -> Agent:
        return Agent(model=config.model, output_type=str)

    agent = init_agent(config)

    with capture_run_messages() as history:
        await agent.run("anything here")

    assert all(
        not m.instructions for m in history if isinstance(m, ModelRequest)
    )


@pytest.mark.agent
@pytest.mark.asyncio
async def test_conditional_microagents_prompt_does_not_trigger(config):
    microagents = [
        MicroAgent("micro_1", "1.0.0", ["MY_AGENT"], ["not_in_prompt"], "should_not_trigger")
    ]

    @conditional_microagents_triggers(microagents)
    @alias_for_microagents("MY_AGENT")
    def init_agent(config: AppConfig) -> Agent:
        return Agent(model=config.model, output_type=str)

    agent = init_agent(config)

    with capture_run_messages() as history:
        await agent.run("no relevant trigger here")

    assert all(
        m.instructions is None or "should_not_trigger" not in m.instructions
        for m in history if isinstance(m, ModelRequest)
    )


@pytest.mark.agent
@pytest.mark.asyncio
async def test_conditional_microagents_two_triggers_matched(config):
    microagents = [
        MicroAgent("A", "1", ["MY_AGENT"], ["foo"], "A"),
        MicroAgent("B", "1", ["MY_AGENT"], ["bar"], "B"),
    ]

    @conditional_microagents_triggers(microagents)
    @alias_for_microagents("MY_AGENT")
    def init_agent(config: AppConfig) -> Agent:
        return Agent(model=config.model, output_type=str)

    agent = init_agent(config)

    with capture_run_messages() as history:
        await agent.run("this has foo and bar triggers")

    assert any(
        "A" in m.instructions and "B" in m.instructions
        for m in history if isinstance(m, ModelRequest) and m.instructions
    )


@pytest.mark.agent
@pytest.mark.asyncio
async def test_conditional_microagents_two_defined_only_one_triggered(config):
    microagents = [
        MicroAgent("A", "1", ["MY_AGENT"], ["foo"], "A"),
        MicroAgent("B", "1", ["MY_AGENT"], ["bar"], "B"),
    ]

    @conditional_microagents_triggers(microagents)
    @alias_for_microagents("MY_AGENT")
    def init_agent(config: AppConfig) -> Agent:
        return Agent(model=config.model, output_type=str)

    agent = init_agent(config)

    with capture_run_messages() as history:
        await agent.run("foo only is here")

    assert any(
        "A" in m.instructions and "B" not in m.instructions
        for m in history if isinstance(m, ModelRequest) and m.instructions
    )

@pytest.mark.agent
@pytest.mark.asyncio
async def test_conditional_microagents_triggered_but_agent_id_not_matching(config):
    microagents = [
        MicroAgent("X", "1", ["OTHER_AGENT"], ["trigger_me"], "X")
    ]

    @conditional_microagents_triggers(microagents)
    @alias_for_microagents("MY_AGENT")
    def init_agent(config: AppConfig) -> Agent:
        return Agent(model=config.model, output_type=str)

    agent = init_agent(config)

    with capture_run_messages() as history:
        await agent.run("trigger_me is in the prompt")

    assert all(
        m.instructions is None or "X" not in m.instructions
        for m in history if isinstance(m, ModelRequest)
    )
