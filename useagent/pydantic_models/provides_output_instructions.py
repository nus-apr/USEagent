from typing import Protocol, runtime_checkable


@runtime_checkable
class ProvidesOutputInstructions(Protocol):
    @classmethod
    def get_output_instructions(cls) -> str:
        """
        Return instructions describing the desired output format.
        These should be specific enough to be provided to an agent that targets this type
        as a return type.
        """
        ...
