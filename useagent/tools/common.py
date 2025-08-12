from pathlib import Path

from useagent.config import ConfigSingleton
from useagent.pydantic_models.tools.errorinfo import ArgumentEntry, ToolErrorInfo


def useagent_guard_rail(
    to_check: str | Path, supplied_arguments: list[ArgumentEntry] = []
) -> ToolErrorInfo | None:
    if isinstance(to_check, Path):
        to_check = str(to_check)
    if (
        ConfigSingleton.is_initialized()
        and ConfigSingleton.config.optimization_toggles["useagent-file-path-guard"]
    ):
        if "useagent" in to_check.lower():
            return ToolErrorInfo(
                message=f"You seem to be working on a USEAgent file ({to_check}), which you are at no point meant to do. Reconsider your working directory and return to the target project.",
                supplied_arguments=supplied_arguments,
            )

    return None
