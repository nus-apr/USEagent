from collections import defaultdict
from dataclasses import dataclass, field
from typing import Literal

from pydantic_ai.models import Model, infer_model
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from useagent.pydantic_models.output.action import Action
from useagent.pydantic_models.output.answer import Answer
from useagent.pydantic_models.output.code_change import CodeChange
from useagent.tasks.github_task import GithubTask
from useagent.tasks.local_task import LocalTask
from useagent.tasks.usebench_task import UseBenchTask


def _default_optimization_toggles() -> dict[str, bool]:
    # Default Dict will return false for any unknown key, but will not give an error.
    return defaultdict(
        bool,
        {
            "meta-agent-speed-bumps": True,
            "check-grep-command-arguments": True,
            "loosen-probing-agent-strictness": True,
            "bash-tool-speed-bumper": True,
            "useagent-stopper-file": False,
            "hide-hidden-folders-from-greps": True,
            "hide-hidden-folders-from-finds": True,
            "useagent-file-path-guard": True,
            "shorten-log-output": True,
            "vcs-agent-answer-instructions": True,
            "reiterate-on-doubts": True,
        },
    )


def _default_context_window_limits() -> dict[str, int]:
    # Int value represents max-length in 'tokens', not in string length.
    # Return '-1' to mark unknown
    return defaultdict(
        lambda: -1,
        {
            "google-gla:gemini-2.5-flash": 1048576,  # As seen in pydantic AI 0.7.5 on 25.08.2025
            # "openai:gpt-5-mini": 272000,  # Looked up on 26.08.2025
            "openai:gpt-5-mini": 100000,  # DevNote: We chose an intentionally lower token limit for cost saving purposes
        },
    )


@dataclass
class AppConfig:
    model: Model
    model_descriptor: str = "UNK"
    output_dir: str | None = None

    optimization_toggles: dict[str, bool] = field(
        default_factory=_default_optimization_toggles
    )

    task_type: Literal[GithubTask, LocalTask, UseBenchTask] = (LocalTask,)
    output_type: Literal[Action, CodeChange, Answer] = CodeChange
    context_window_limits: dict[str, int] = field(
        default_factory=_default_context_window_limits
    )

    def lookup_model_context_window(self) -> int:
        return self.context_window_limits[self.model_descriptor]


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
        task_type: Literal[GithubTask, LocalTask, UseBenchTask] = LocalTask,
        output_type: Literal[Action, CodeChange, Answer] = CodeChange,
    ):
        if cls._instance is not None:
            raise RuntimeError("Config already initialized")

        model_desc = "UNK"
        if isinstance(model, str):
            model_desc = model
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

        cls._instance = AppConfig(
            model=model,
            output_dir=output_dir,
            task_type=task_type,
            output_type=output_type,
            model_descriptor=model_desc,
        )

    @classmethod
    def reset(cls):
        cls._instance = None

    @classmethod
    def is_initialized(cls):
        return cls._instance is not None
