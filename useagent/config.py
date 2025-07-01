from typing import Optional
from dataclasses import dataclass

from pydantic_ai.models import Model,infer_model
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider


@dataclass
class AppConfig:
    model: Model
    output_dir: str | None = None


class _LazyProxy:
    """Lazily forwards attribute access to the real AppConfig once initialized."""
    def __getattr__(self, name):
        instance = ConfigSingleton._instance
        if instance is None:
            raise RuntimeError(f"Config has not been initialized, cannot access `{name}`.")
        return getattr(instance, name)


class ConfigSingleton:
    _instance: Optional[AppConfig] = None
    config = _LazyProxy()  # public interface

    @classmethod
    def init(cls, model: str | Model, output_dir: str | None = None, provider_url: str | None = None):
        if cls._instance is not None:
            raise RuntimeError("Config already initialized")

        if isinstance(model, str):
            if model.startswith("ollama:"):
                model_name = model.split(":", 1)[1]
                if not provider_url:
                    raise ValueError("provider_url required for ollama models")
                model = OpenAIModel(
                    model_name=model_name,
                    provider=OpenAIProvider(base_url=provider_url, api_key="ollama-dummy")
                )
            else:
                model = infer_model(model)

        cls._instance = AppConfig(model=model, output_dir=output_dir)

    @classmethod
    def reset(cls):
        cls._instance = None
