from pydantic.dataclasses import dataclass

from useagent.pydantic_models.common.constrained_types import NonEmptyStr


@dataclass
class TestResult:
    __test__ = False  # This is to not get warnings from pytest discovery because the Class & File are prefixed with `test`.

    executed_test_command: NonEmptyStr
    test_successful: bool
    rationale: NonEmptyStr

    selected_test_output: NonEmptyStr | None = None
    doubts: NonEmptyStr | None = None

    @classmethod
    def get_output_instructions(cls) -> str:
        return """
        A `TestResult` consists of:

        - `executed_test_command`: `str`, the final executed test-command, that you used to derive your test results and judgement presented in this TestResult. Do not fabricate any commands you have not executed. 
        - `test_successful`: `bool`, whether you see that the (relevant) tests pass. 
        - `rationale`: `NonEmptyStr`, a summary of why you think the tests were successful or not.  
        - `selected_test_output`: `NonEmptyStr` or None, Optional - show artifacts from test execution to support your claims. 
        - doubts: `NonEmptyStr` or None. Optionally, if you think there are any counter arguments to what you have done, or necessary steps missed, or other anomalies, present them here. Keep this based on facts, and do not raise generic doubts.
        """
