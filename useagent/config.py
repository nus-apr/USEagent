from dataclasses import dataclass

from pydantic_ai.models import Model, infer_model
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider


@dataclass
class AppConfig:
    model: Model
    output_dir: str | None = None


class ConfigSingleton:
    _instance: AppConfig | None = None

    @property
    def config(self) -> AppConfig:
        """Returns the current configuration instance."""
        if self._instance is None:
            raise RuntimeError("Config has not been initialized.")
        return self._instance

    @classmethod
    def init(
        cls,
        model: str | Model,
        output_dir: str | None = None,
        provider_url: str | None = None,
    ):
        if cls._instance is not None:
            raise RuntimeError("Config already initialized")

        if isinstance(model, str):
            if model.startswith("ollama:"):
                model_name = model.split(":", 1)[1]
                if not provider_url:
                    raise ValueError("provider_url required for ollama models")
                model = OpenAIModel(
                    model_name=model_name,
                    provider=OpenAIProvider(
                        base_url=provider_url, api_key="ollama-dummy"
                    ),
                )
            else:
                model = infer_model(model)

        cls._instance = AppConfig(model=model, output_dir=output_dir)

    @classmethod
    def reset(cls):
        cls._instance = None
