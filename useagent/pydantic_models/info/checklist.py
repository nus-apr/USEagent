from pydantic.dataclasses import dataclass

from useagent.pydantic_models.common.constrained_types import NonEmptyStr


@dataclass(frozen=False)
class CheckList:
    """
    This dataclass embodies a 'checklist' of steps to verify at the end (or intermediate) of agentic trajectories.
    The goal is that we derive a simple 'yes / no / don't know' to present to the agent.

    Not all tasks must have all boxes checked - if your tasks does not need an installation, then it can be completed without.

    The 'yes / no / don't know' is embodied by having Optional as the 'don't know'.

    The findings might deprecate or change over the trajectory. That is expected and the checklist-agent is instructed to pay respect to the history.
    """

    has_successfully_installed_system_dependencies: bool | None = None
    has_successfully_install_project_dependencies: bool | None = None

    has_successfully_build_project: bool | None = None

    # DevNote: Successfully means there was no hard error, i.e. the test-suite starts running (might have test failures)
    has_successfully_invoked_unit_tests: bool | None = None
    has_successfully_invoked_all_tests: bool | None = None

    has_test_errors: bool | None = None
    observed_test_errors: NonEmptyStr | None = None
    has_test_failures: bool | None = None
    observed_test_failures: NonEmptyStr | None = None

    has_changed_or_edited_files: bool | None = None
    file_changes_have_been_transferred_to_diff_store: bool | None = None

    re_occurring_errors: NonEmptyStr | None = None
    agent_has_attempted_error_repair: bool | None = None

    @classmethod
    def get_output_instructions(cls) -> str:
        return """
A Checklist has the following fields:

Fields
- has_successfully_installed_system_dependencies: bool | None
  True if system-level packages/tools installed without hard errors; False if attempted and failed; None if not known/not attempted.

- has_successfully_install_project_dependencies: bool | None
  True if project/package-manager dependencies installed without hard errors; False if attempted and failed; None if not known/not attempted.

- has_successfully_build_project: bool | None
  True if the project built/compiled successfully; False if build attempted and failed; None if not known/not attempted.

- has_successfully_invoked_unit_tests: bool | None
  True if unit tests were invoked successfully (runner started; failures allowed); False if invocation failed; None if not known/not attempted.

- has_successfully_invoked_all_tests: bool | None
  True if full test suite was invoked successfully (failures allowed); False if invocation failed; None if not known/not attempted.

- has_test_errors: bool | None
  True if hard errors (e.g., import/runtime/errors preventing execution) occurred; False if no such errors observed; None if not known/not observed.

- observed_test_errors: NonEmptyStr | None
  Short summary of representative error(s) when has_test_errors is True (e.g., first error line or message). None if no errors/unknown.

- has_test_failures: bool | None
  True if test assertions failed; False if no failures observed; None if not known/not observed.

- observed_test_failures: NonEmptyStr | None
  Short summary of representative failure(s) when has_test_failures is True. None if no failures/unknown.

- has_changed_or_edited_files: bool | None
  True if the agent changed files; False if confirmed no changes; None if not known/not checked.

- file_changes_have_been_transferred_to_diff_store: bool | None
  True if changes were saved to the diff store; False if attempted and not saved; None if not known/not attempted.

- re_occurring_errors: NonEmptyStr | None
  Brief description of any recurring error pattern observed across steps. None if none/unknown.

- agent_has_attempted_error_repair: bool | None
  True if the agent explicitly attempted to repair errors; False if did not; None if not known.

Notes
- "Successfully" means no hard error blocked the step; test failures are allowed where stated. A test that fails due to imports is considered unsuccessful. 
-  A value of None means "unknown / not observed yet" (not a negative). Values may be revised later as more evidence appears.
"""
