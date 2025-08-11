from collections import defaultdict
from dataclasses import dataclass, field

from pydantic_ai.models import Model, infer_model
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider


def _default_optimization_toggles() -> dict[str, bool]:
    # Default Dict will return false for any unknown key, but will not give an error.
    return defaultdict(
        bool,
        {
            "meta-agent-speed-bumps": True,
            "check-grep-command-arguments": True,
            "loosen-probing-agent-strictness": True,
            "bash-tool-speed-bumper": True,
            "useagent-stopper-file": True,
        },
    )


@dataclass
class AppConfig:
    model: Model
    output_dir: str | None = None

    optimization_toggles: dict[str, bool] = field(
        default_factory=_default_optimization_toggles
    )


class ConfigSingleton:
    _instance: AppConfig | None = None

    class classproperty:
        def __init__(self, fget):
            self.fget = fget

        def __get__(self, obj, owner):
            return self.fget(owner)

    @classproperty
    def config(cls) -> AppConfig:
        """Returns the current configuration instance."""
        if cls._instance is None:
            raise RuntimeError(
                "Config has not been initialized. Must call ConfigSingleton.init() first."
            )
        return cls._instance

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

    @classmethod
    def is_initialized(cls):
        return cls._instance is not None
