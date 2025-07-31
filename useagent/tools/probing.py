from loguru import logger
from pydantic_ai import RunContext

from useagent.pydantic_models.info.environment import Environment
from useagent.pydantic_models.info.partial_environment import PartialEnvironment


def check_and_report_environment(ctx: RunContext[PartialEnvironment]) -> Environment:
    """
    Try to form a Environment from the current PartialEnvironment.
    Will return a Environment upon success, or raise a ValueError if any fields are missing.

    Returns:
        Environment: The accumulated environment info in the PartialEnvironment presented.
    """
    logger.info("[Tool] Invoked check_and_report_environment")
    partial_environment: PartialEnvironment = ctx.deps
    return _check_and_report_environment(partial_environment)


def _check_and_report_environment(
    partial_environment: PartialEnvironment,
) -> Environment:
    if not partial_environment.is_complete():
        raise ValueError(
            f"The given partial environment was not complete and is missing entries. Missing entries: [{','.join(partial_environment.get_missing_fields())}]"
        )
    # Note: The .to_environment() will call the constructor including all validators assigned to a Environment.
    # In case of ValueErrors, these will appear here and bubble up into the normal Workflow.
    return partial_environment.to_environment()
