from pydantic.dataclasses import dataclass

from useagent.pydantic_models.common.constrained_types import NonEmptyStr
from useagent.pydantic_models.info.environment import Environment


@dataclass
class Answer:
    answer: NonEmptyStr
    explanation: NonEmptyStr
    doubts: NonEmptyStr | None
    environment: Environment | None

    @classmethod
    def get_output_instructions(cls) -> str:
        return (
            """
        An `Answer` consists of the following fields: 

        - answer (Non Empty String): The answer to the question you were asked.
        - explanation (Non Empty String): Describe what you have done, why you consider the answer sufficient and
        - doubts (Non Empty String, or None): Optionally, if you think there are any counter arguments to what you have done, or necessary steps missed, or other anomalies, present them here.
                Keep this based on facts, and do not raise generic doubts. If there are doubts about installations and dependencies, stick to your environment and don't extrapolate to possible different environments.
                When describing your doubts, do not use any references or links to previous messages - describe all elements, their locations, etc. as if to a person that sees this conversation and artifact from a blank slate. 
        - environment (Environment, or None): Optionally, if you can, provide an environment you detected for which this answer holds. Especially take this into account if the answer seems very related to the environment.
        
        """
            + Environment.get_output_instructions()
        )  # Also add instructions from how the diff-entry looks like.
