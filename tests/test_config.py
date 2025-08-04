import pytest
from openai import OpenAIError
from pydantic_ai.exceptions import UserError

from useagent.config import ConfigSingleton


@pytest.fixture(autouse=True)
def reset_config():
    ConfigSingleton.reset()
    yield
    ConfigSingleton.reset()


def test_llama_no_url_fails():
    with pytest.raises(UserError):
        ConfigSingleton.init("llama3.3:70b")


def test_llama_with_url_fails():
    with pytest.raises(UserError):
        ConfigSingleton.init("llama3.3:70b", provider_url="http://localhost:11434/v1")


def test_ollama_with_url_passes():
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    assert ConfigSingleton.config.model


def test_ollama_with_extra_colon_fails():
    with pytest.raises(ValueError):
        ConfigSingleton.init("ollama:llama3.3:70")


def test_gemini_no_key_fails(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(UserError):
        ConfigSingleton.init("google-gla:gemini-2.0-flash")


def test_gemini_with_key_passes(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    ConfigSingleton.init("google-gla:gemini-2.0-flash")
    assert ConfigSingleton.config.model


def test_openai_no_key_fails(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(OpenAIError):
        ConfigSingleton.init("openai:gpt-4o")


def test_openai_with_key_passes(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    ConfigSingleton.init("openai:gpt-4o")
    assert ConfigSingleton.config.model


def test_uninitialized_access_fails():
    with pytest.raises(RuntimeError):
        _ = ConfigSingleton.config.model


def test_reset_allows_reinit(monkeypatch):
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.reset()
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    ConfigSingleton.init("openai:gpt-4o")
    assert "openai" in str(ConfigSingleton.config.model.__class__).lower()


def test_init_should_have_non_empty_optimization_toggles():
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    assert ConfigSingleton.config.optimization_toggles
    assert (
        ConfigSingleton.config.optimization_toggles["check-grep-command-arguments"]
        is True
    )


def test_get_should_return_false_for_unknown_key():
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    assert ConfigSingleton.config.optimization_toggles["non-existent-flag"] is False


def test_add_and_get_should_return_correct_value():
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    flags = ConfigSingleton.config.optimization_toggles
    flags["new-flag"] = True
    flags["other-flag"] = False
    assert flags["new-flag"] is True
    assert flags["other-flag"] is False


def test_reset_should_restore_default_flags():
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["temp-flag"] = True
    ConfigSingleton.reset()
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    assert ConfigSingleton.config.optimization_toggles["temp-flag"] is False
