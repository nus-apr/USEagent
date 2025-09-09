from pydantic.dataclasses import dataclass

from useagent.pydantic_models.common.constrained_types import NonEmptyStr
from useagent.pydantic_models.info.environment import Environment


@dataclass
class CheckList:
    install_system_dependencies: bool = False
    install_dependencies: bool = False
    build: bool = False
    unit_tests: bool = False

    @classmethod
    def get_output_instructions(cls) -> str:
        return (
            """
        An `CheckList` consists of the following fields: 

        - install_system_dependencies: If system level dependencies are installed.
        - install_dependencies: If other dependencies are installed such as language specific packages.
        - build: if the project has been built (compiled) successfully.
        - unit_tests: if tests have been executed.
        """
            + Environment.get_output_instructions()
        )
