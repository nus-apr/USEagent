import pytest
from pydantic import ValidationError

from useagent.pydantic_models.info.environment import Commands


@pytest.mark.pydantic_model
@pytest.mark.parametrize("cmd", ["make build", " make build ", "\tbuild\n"])
def test_valid_optional_commands(cmd: str):
    Commands(
        build_command=cmd,
        test_command=cmd,
        run_command=cmd,
        linting_command=cmd,
        reducable_test_scope=True,
        example_reduced_test_command=cmd,
        can_install_system_packages=True,
        system_package_manager="apt",
        can_install_project_packages=True,
        project_package_manager="pip",
        other_important_commands=["cmd1", "cmd2"],
    )


@pytest.mark.pydantic_model
@pytest.mark.parametrize(
    "cmd_field",
    [
        "build_command",
        "test_command",
        "run_command",
        "linting_command",
        "example_reduced_test_command",
        "system_package_manager",
        "project_package_manager",
    ],
)
@pytest.mark.parametrize("bad_value", ["", " ", "\t", "\n"])
def test_invalid_optional_command_fields(cmd_field: str, bad_value: str):
    kwargs = {
        "build_command": None,
        "test_command": None,
        "run_command": None,
        "linting_command": None,
        "reducable_test_scope": False,
        "example_reduced_test_command": None,
        "can_install_system_packages": False,
        "system_package_manager": None,
        "can_install_project_packages": False,
        "project_package_manager": None,
        "other_important_commands": [],
    }
    kwargs[cmd_field] = bad_value
    with pytest.raises(ValidationError):
        Commands(**kwargs)


@pytest.mark.pydantic_model
@pytest.mark.parametrize("cmds", [["cmd1", " cmd2 "], ["\tbuild", "test"]])
def test_valid_other_important_commands(cmds: list[str]):
    Commands(other_important_commands=cmds)


@pytest.mark.pydantic_model
@pytest.mark.parametrize("cmds", [["", "cmd"], ["  ", "\n"]])
def test_invalid_other_important_commands(cmds: list[str]):
    with pytest.raises(ValidationError):
        Commands(other_important_commands=cmds)


@pytest.mark.pydantic_model
def test_all_commands_none_and_empty_other_raises():
    with pytest.raises(ValidationError):
        Commands()


@pytest.mark.pydantic_model
def test_one_command_present_is_valid():
    Commands(build_command="make")


@pytest.mark.pydantic_model
def test_other_commands_nonempty_is_valid():
    Commands(other_important_commands=["run.sh"])


@pytest.mark.pydantic_model
def test_known_commands_removed_from_other():
    c = Commands(
        build_command="make",
        test_command="pytest",
        other_important_commands=["make", "deploy", "pytest", " status "],
    )
    assert sorted(c.other_important_commands) == ["deploy", "status"]


@pytest.mark.pydantic_model
def test_get_output_instructions_should_not_return_none():
    assert Commands.get_output_instructions()
