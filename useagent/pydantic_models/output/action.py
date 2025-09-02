from pydantic.dataclasses import dataclass

from useagent.pydantic_models.common.constrained_types import NonEmptyStr
from useagent.pydantic_models.tools.cliresult import CLIResult
from useagent.pydantic_models.tools.errorinfo import ToolErrorInfo


@dataclass
class Action:
    success: bool
    evidence: NonEmptyStr
    execution_artifact: CLIResult | ToolErrorInfo | None
    doubts: NonEmptyStr | None = None

    @classmethod
    def get_output_instructions(cls) -> str:
        return """
        The `Action` is a summary of an action you performed, and has the following attributes:

        - success (bool): True if you think the action was performed correctly. 
        - evidence (Non Empty String): Provide evidence and arguments for what you have done, and how you achieve your verdicts of `success`
        - execution_artifact: If possible, look for CLIResults or ToolErrorInfos from the Commands you have been executing.
        - doubts (Non Empty String, or None): Optionally, if you think there are any counter arguments to what you have done, or necessary steps missed, or other anomalies, present them here. Keep this based on facts, and do not raise generic doubts. If there are doubts about installations and dependencies, stick to your environment and don't extrapolate to possible different environments.

        When constructing this object, focus on the most recent actions. 
        Especially initial steps you performed while exploring the repository, or actions that you were able to correct in later iterations, might not be relevant.
        """  # TODO: Do we want to add infos on CLI_Output + ToolErrorInfo here?
