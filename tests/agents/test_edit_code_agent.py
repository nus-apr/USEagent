import pytest
from pydantic_ai import capture_run_messages, models
from pydantic_ai.models.test import TestModel

from useagent.agents.edit_code.agent import init_agent
from useagent.config import AppConfig
from useagent.pydantic_models.task_state import TaskState
from useagent.state.git_repo import GitRepository
from useagent.tasks.test_task import TestTask

models.ALLOW_MODEL_REQUESTS = False

EXAMPLE_GIT_DIFF_NEW_FILE_ONE_LINE = """\
diff --git a/newfile.txt b/newfile.txt
new file mode 100644
index 0000000..e69de29
--- /dev/null
+++ b/newfile.txt
@@ -0,0 +1 @@
+Hello world
"""


@pytest.mark.agent
def test_edit_agent_has_instructions_prompts():
    test_model = TestModel(
        call_tools=["view"],
        custom_output_args={"file_path": "./README.md", "view_range": None},
    )
    config = AppConfig(model=test_model)
    agent = init_agent(config)

    # DevNote:
    # This is not a really sophisticated test. the TestModel will call ALL tools,
    # which will just trigger errors
    # This means that a agent.run() is currently not suggested.
    # its also not really possible to pass arguments, at least not to my knowledge.

    assert len(agent._instructions) >= 1


@pytest.mark.agent
@pytest.mark.asyncio
async def test_edit_agent_direct_output_no_tool_calls__example_scaffold_test(tmp_path):
    """
    DevNote: This is a *very simple* test that just ignores all tool calls.
    It is to be a an example to easily copy paste for other agents and show how to access the history.
    For more complex tests, the tool calls must be faked, likely also the tools be overwritten with mocks.
    """
    # expected_output = DiffEntry(
    #    diff_content=EXAMPLE_GIT_DIFF_NEW_FILE_ONE_LINE, notes="some notes"
    # )
    expected_output = "diff_0"

    test_model = TestModel(call_tools=[], custom_output_args=expected_output)
    config = AppConfig(model=test_model)
    agent = init_agent(config)

    state = TaskState(
        task=TestTask(root=".", issue_statement="Fix bug in foo.py"),
        # Note Issue#1: I had `.` here and it replaced my git user name in the repository level upon running tests.
        git_repo=GitRepository(local_path=tmp_path),
    )

    with capture_run_messages() as history:
        result = await agent.run("fix the bug", deps=state)

    for message in history:
        # DevNote: Kept here to show how to access it in a test.
        print("History:", message)

    assert result
    assert history and len(history) > 1
