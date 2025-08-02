from dataclasses import field

from pydantic.dataclasses import dataclass

from useagent.pydantic_models.common.constrained_types import NonEmptyStr
from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo


@dataclass
class Action:
    success: bool
    evidence: NonEmptyStr
    cli_output: list[CLIResult] = field(default_factory=list)
    errors: list[ToolErrorInfo] = field(default_factory=list)
    doubts: NonEmptyStr | None = None

    @classmethod
    def get_output_instructions(cls) -> str:
        return """
        The `Action` is a summary of an action you performed, and has the following attributes:

        - success (bool): True if you think the action was performed correctly. 
        - evidence (Non Empty String): Provide evidence and arguments for what you have done, and how you achieve your verdicts of `success`
        - cli_output (List[CLIResult]): If possible, provide a record of the CLI Actions you have done. Limit this to only the most relevant and recent activities
        - errors (List[ToolErrorInfo]): A list of (relevant!) ToolErrors, to support the final evidence and success. Limit this to only the most relevant and recent errors.
        - doubts (Non Empty String, or None): Optionally, if you think there are any counter arguments to what you have done, or necessary steps missed, or other anomalies, present them here.

        When constructing this object, focus on the most recent actions. 
        Especially initial steps you performed while exploring the repository, or actions that you were able to correct in later iterations, might not be relevant.
        """  # TODO: Do we want to add infos on CLI_Output + ToolErrorInfo here?
