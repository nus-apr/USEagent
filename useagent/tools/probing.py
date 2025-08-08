from loguru import logger
from pydantic_ai import RunContext

from useagent.pydantic_models.info.environment import Environment
from useagent.pydantic_models.info.partial_environment import PartialEnvironment


def check_environment(ctx: RunContext[PartialEnvironment]) -> str:
    """
    Check the current PartialEnvironment for missing fields.

    Returns:
        str: Either a short confirmation that the PartialEnvironment is complete, or a list of the missing entries.
    """
    logger.info("[Tool] Invoked check_environment")
    partial_environment: PartialEnvironment = ctx.deps
    return _check_environment(partial_environment)


def _check_environment(partial_environment: PartialEnvironment) -> str:
    if not partial_environment.is_complete():
        logger.debug(
            f"[Tool] check environment reports the following fields still missing: { [{','.join(partial_environment.get_missing_fields())}]}"
        )
        return f"The given partial environment is not complete and is missing entries. Missing entries: [{','.join(partial_environment.get_missing_fields())}]"
    else:
        return "The partial environment is well-formed and can be reported."


def report_environment(ctx: RunContext[PartialEnvironment]) -> Environment:
    """
    Try to form a Environment from the current PartialEnvironment.
    Will return a Environment upon success, or raise a ValueError if any fields are missing.

    Returns:
        Environment: The accumulated environment info in the PartialEnvironment presented.
    """
    logger.info("[Tool] Invoked report_environment")
    partial_environment: PartialEnvironment = ctx.deps
    return _report_environment(partial_environment)


def _report_environment(
    partial_environment: PartialEnvironment,
) -> Environment:
    if not partial_environment.is_complete():
        raise ValueError(
            f"The given partial environment was not complete and is missing entries. Missing entries: [{','.join(partial_environment.get_missing_fields())}]"
        )
    # Note: The .to_environment() will call the constructor including all validators assigned to a Environment.
    # In case of ValueErrors, these will appear here and bubble up into the normal Workflow.
    return partial_environment.to_environment()
