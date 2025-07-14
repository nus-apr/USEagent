import pytest

from useagent.agents.edit_code.agent import init_agent as init_edit_agent
from useagent.agents.meta.agent import init_agent as init_meta_agent
from useagent.agents.search_code.agent import init_agent as init_search_agent

from useagent.microagents.decorators import alias_for_microagents

from useagent.config import AppConfig

from pydantic_ai.agent import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.test import TestModel

@pytest.fixture
def dummy_config() -> AppConfig:
    model = OpenAIModel(
        model_name="llama3.2",
        provider=OpenAIProvider(base_url="http://localhost:11434", api_key="ollama-dummy")
    )
    return AppConfig(model=model)


@pytest.mark.agent
def test_alias_for_microagents_sets_agent_id_for_edit(dummy_config):
    agent = init_edit_agent(config=dummy_config)
    print(agent.__dataclass_fields__)
    assert hasattr(agent, "agent_id")
    assert agent.agent_id == "EDIT"

@pytest.mark.agent
def test_alias_for_microagents_sets_agent_id_for_search(dummy_config):
    agent = init_search_agent(config=dummy_config)
    assert hasattr(agent, "agent_id")
    assert agent.agent_id == "SEARCH"

@pytest.mark.agent
def test_alias_for_microagents_sets_agent_id_for_meta(dummy_config):
    agent = init_meta_agent(config=dummy_config)
    assert hasattr(agent, "agent_id")
    assert agent.agent_id == "META"


@pytest.mark.agent
def test_alias_for_microagents_decorator_sets_attribute(dummy_config):
    @alias_for_microagents("DUMMY")
    def init_agent(config: AppConfig) -> Agent:
        return Agent(model=config.model, output_type=str)

    agent = init_agent(dummy_config)
    assert hasattr(agent, "agent_id")
    assert agent.agent_id == "DUMMY"


@pytest.mark.agent
def test_no_decorator_means_no_agent_id(dummy_config):
    def init_agent(config: AppConfig) -> Agent:
        return Agent(model=config.model, output_type=str)

    agent = init_agent(dummy_config)
    assert not hasattr(agent, "agent_id")


@pytest.mark.agent
def test_decorator_sets_agent_id_even_if_name_is_set(dummy_config):
    @alias_for_microagents("DECORATOR_ID")
    def init_agent(config: AppConfig) -> Agent:
        return Agent(model=config.model, output_type=str, name="AGENT_NAME")

    agent = init_agent(dummy_config)
    assert hasattr(agent, "agent_id")
    assert agent.agent_id == "DECORATOR_ID"
    assert agent.name == "AGENT_NAME"


@pytest.mark.agent
@pytest.mark.parametrize("bad_value", [None, "", "   "])
def test_alias_for_microagents_rejects_invalid_values(bad_value):
    with pytest.raises(ValueError):
        @alias_for_microagents(bad_value)
        def init_agent(config: AppConfig) -> Agent:
            return Agent(model=config.model, output_type=str)


@pytest.mark.agent
def test_multiple_alias_decorators_apply_outermost(dummy_config):
    @alias_for_microagents("OUTER")
    @alias_for_microagents("INNER")
    def init_agent(config: AppConfig) -> Agent:
        return Agent(model=config.model, output_type=str)

    agent = init_agent(dummy_config)
    assert hasattr(agent, "agent_id")
    assert agent.agent_id == "OUTER"
