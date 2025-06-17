from typing import Optional
from dataclasses import dataclass


@dataclass
class AppConfig:
    model: str
    provider_url: str | None = None # Used for Local Ollama Models and other self-hosted entities, not needed for commercial APIs
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
    def init(cls, model: str, output_dir: str | None = None, provider_url: str | None = None):
        if cls._instance is not None:
            raise RuntimeError("Config already initialized")
        cls._instance = AppConfig(model=model, output_dir=output_dir)

    @classmethod
    def reset(cls):
        cls._instance = None
