# test_useagent_guard_rail.py
from pathlib import Path

import pytest

from useagent.common.guardrails import useagent_guard_rail
from useagent.config import ConfigSingleton
from useagent.pydantic_models.tools.errorinfo import ArgumentEntry


@pytest.fixture(autouse=True)
def reset_config_each_test():
    ConfigSingleton.reset()
    yield
    ConfigSingleton.reset()


@pytest.mark.parametrize(
    "text",
    [
        "useagent",
        "UseAgent",
        "/tmp/UseAgent/data.txt",
        "C:\\work\\project\\USEAGENT_config.yaml",
        "python -m useagent.cli",
        "bash scripts/useAgent.sh",
        "git add useagent_config.json",
        "rm -rf ./tools/useagent",
        "code useagent/main.py",
        "../../useagent/README.md",
        "../useagent/.venv/",
    ],
)
def test_contains_useagent_text_should_return_error(text: str) -> None:
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["real toggle"] = True
    ConfigSingleton.config.optimization_toggles["useagent-file-path-guard"] = True

    res = useagent_guard_rail(text, supplied_arguments=[])
    assert res is not None
    assert "USEAgent file" in res.message
    assert text in res.message
    assert getattr(res, "supplied_arguments", None) == []


@pytest.mark.parametrize(
    "text",
    [
        "",
        "project/readme.md",
        "/opt/app/main.py",
        "python -m app.cli",
        "git add src/module/file.txt",
        "docs/user_guide.pdf",
        "/var/tmp/usagent/data.txt",  # missing the 'e'
        "USEAG NT_config.yaml",  # broken spacing
    ],
)
def test_without_useagent_text_should_return_none(text: str) -> None:
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["real toggle"] = True
    ConfigSingleton.config.optimization_toggles["useagent-file-path-guard"] = True

    assert useagent_guard_rail(text) is None


def test_contains_useagent_path_should_return_error() -> None:
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["real toggle"] = True
    ConfigSingleton.config.optimization_toggles["useagent-file-path-guard"] = True

    p: Path = Path("/var/tmp/UseAgent/session.log")
    res = useagent_guard_rail(p, supplied_arguments=[])
    assert res is not None
    assert "/var/tmp/UseAgent/session.log" in res.message


def test_guard_disabled_should_return_none() -> None:
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["real toggle"] = True
    ConfigSingleton.config.optimization_toggles["useagent-file-path-guard"] = False

    assert useagent_guard_rail("some/UseAgent/file.txt") is None


def test_not_initialized_should_return_none() -> None:
    # Fixture leaves it uninitialized here.
    assert useagent_guard_rail("tools/useagent/x.py") is None


def test_supplied_arguments_should_preserve_reference() -> None:
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["real toggle"] = True
    ConfigSingleton.config.optimization_toggles["useagent-file-path-guard"] = True

    args: list[ArgumentEntry] = [ArgumentEntry("cmd", "python -m useagent.cli")]
    res = useagent_guard_rail("useagent/run.py", supplied_arguments=args)
    assert res is not None
    assert res.supplied_arguments is not None


def test_case_insensitive_should_return_error() -> None:
    ConfigSingleton.init("ollama:llama3.3", provider_url="http://localhost:11434/v1")
    ConfigSingleton.config.optimization_toggles["real toggle"] = True
    ConfigSingleton.config.optimization_toggles["useagent-file-path-guard"] = True

    assert useagent_guard_rail("paTh/UsEaGeNt/x.py") is not None
