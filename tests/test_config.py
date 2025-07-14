import pytest
from useagent.config import ConfigSingleton

from pydantic_ai.models import Model,infer_model
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.exceptions import UserError
from openai import OpenAIError

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
