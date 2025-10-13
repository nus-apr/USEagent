import os
import sys
from argparse import ArgumentParser, ArgumentTypeError, Namespace
from pathlib import Path
from tempfile import mkdtemp
from typing import Literal

from loguru import logger

from useagent import task_runner
from useagent.config import AppConfig, ConfigSingleton
from useagent.pydantic_models.output.action import Action
from useagent.pydantic_models.output.answer import Answer
from useagent.pydantic_models.output.code_change import CodeChange
from useagent.flags import USEBENCH_ENABLED
from useagent.tasks.github_task import GithubTask
from useagent.tasks.local_task import LocalTask
from useagent.tasks.swebench_task import SWEbenchTask
from useagent.tasks.task import Task
from useagent.tasks.usebench_loader import UseBenchTask


def add_common_args(parser: ArgumentParser) -> None:
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Path to the directory that stores the run results.",
    )

    parser.add_argument(
        "--output-type",
        type=parse_output_type,
        default=CodeChange,
        help="Output model type to use. Options: answer, action, codechange.",
    )

    parser.add_argument(
        "--model",
        type=str,
        default="google-gla:gemini-2.0-flash",
        help="Model identifier to use.",
    )

    parser.add_argument(
        "--provider-url",
        type=str,
        default=None,
        help="URL for locally hosted instances like Ollama.",
    )

    parser.add_argument(
        "--task-id",
        type=str,
        help="Unique identifier for the task run.",
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="The log level user for loguru logging to the console.",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="If specified, a DEBUG level log will be logger to this location.",
    )


def set_usebench_parser_args(parser: ArgumentParser) -> None:
    add_common_args(parser)

    parser.add_argument(
        "--task-list-file",
        type=str,
        help="Path to the file that contains all tasks ids to be run.",
    )


def set_local_parser_args(parser: ArgumentParser) -> None:
    add_common_args(parser)

    parser.add_argument(
        "--project-directory",
        type=Path,
        help="Path to the folder containing the project to operate on.",
    )

    task_group = parser.add_mutually_exclusive_group(required=True)
    task_group.add_argument(
        "--task-description",
        type=str,
        help="Verbatim description of what should be done.",
    )
    task_group.add_argument(
        "--task-file",
        type=Path,
        help="A path to a markdown or text file containing the task.",
    )


def set_github_parser_args(parser: ArgumentParser) -> None:
    add_common_args(parser)
    parser.add_argument(
        "--repo-url",
        type=str,
        required=True,
        help="Git repository to clone (SSH or HTTPS).",
    )
    parser.add_argument(
        "--working-dir",
        type=Path,
        default=Path("/tmp/working_dir"),
        help="Target directory to clone into and work on (within Docker Container).",
    )
    parser.add_argument(
        "--commit",
        type=str,
        required=False,
        help="Commit SHA to checkout and branch from.",
    )

    task_group = parser.add_mutually_exclusive_group(required=True)
    task_group.add_argument(
        "--task-description",
        type=str,
        help="Verbatim description of what should be done.",
    )
    task_group.add_argument(
        "--task-file",
        type=Path,
        help="A path to a markdown or text file containing the task.",
    )


def set_swebench_parser_args(parser: ArgumentParser) -> None:
    add_common_args(parser)
    parser.add_argument(
        "--instance-id",
        type=str,
        required=True,
        help="SWE-bench instance_id to materialize.",
    )
    parser.add_argument(
        "--working-dir",
        type=Path,
        default=SWEbenchTask.get_default_working_dir(),
        help="Target directory to clone into and work on (within Docker Container).",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="princeton-nlp/SWE-bench_Verified",
        help="HF dataset name containing the instance.",
    )
    parser.add_argument(
        "--split",
        type=str,
        default="test",
        choices=["train", "validation", "test"],
        help="Dataset split to search for the instance.",
    )


def _get_task_description(args: Namespace) -> str:
    if getattr(args, "task_description", None):
        return args.task_description
    if getattr(args, "task_file", None) and args.task_file.is_file():
        return args.task_file.read_text()
    raise ValueError("Invalid task file")


def parse_args():
    parser = ArgumentParser()

    subparser_dest_attr_name = "command"
    subparsers = parser.add_subparsers(dest=subparser_dest_attr_name)

    # TODO: add a common parser for all other kinds of tasks

    usebench_parser = subparsers.add_parser(
        "usebench", help="Run one or multiple usebench tasks."
    )
    set_usebench_parser_args(usebench_parser)

    local_parser = subparsers.add_parser(
        "local", help="Run a task from a description or file."
    )
    set_local_parser_args(local_parser)

    github_parser = subparsers.add_parser(
        "github", help="Run a task on a GitHub repository, from a provided URL."
    )
    set_github_parser_args(github_parser)

    swebench_parser = subparsers.add_parser(
        "swebench", help="Materialize and run a SWE-bench (verified) instance by id."
    )
    set_swebench_parser_args(swebench_parser)

    return parser.parse_args(), subparser_dest_attr_name


def handle_command(args: Namespace, subparser_dest_attr_name: str) -> None:
    subcommand = getattr(args, subparser_dest_attr_name, None)
    if subcommand == "usebench":
        if not USEBENCH_ENABLED or UseBenchTask is None:
            raise ValueError(
                "USEBench is not enabled. Set USEBENCH_ENABLED=true and install extras: uv sync --extra usebench"
            )
        uid = args.task_id
        local_path = mkdtemp(prefix=f"acr_usebench_{uid}")
        usebench_task = UseBenchTask(
            uid=uid,
            project_path=local_path,
        )
        task_runner.run(usebench_task, args.output_dir, output_type=CodeChange)

    elif subcommand == "local":
        local_path = args.project_directory
        task_desc = _get_task_description(args)
        local_task = LocalTask(issue_statement=task_desc, project_path=local_path)
        task_runner.run(local_task, args.output_dir, output_type=args.output_type)

    elif subcommand == "github":
        task_desc = _get_task_description(args)
        task = GithubTask(
            issue_statement=task_desc,
            repo_url=args.repo_url,
            working_dir=args.working_dir,
            commit=args.commit,
        )
        task_runner.run(task, args.output_dir, output_type=args.output_type)

    elif subcommand == "swebench":
        task = SWEbenchTask(
            instance_id=args.instance_id,
            working_dir=args.working_dir,
            dataset=args.dataset,
            split=args.split,
        )
        # issue_statement is derived from the dataset; task.uid is instance_id
        task_runner.run(task, args.output_dir, output_type=args.output_type)

    else:
        raise ValueError(f"Unknown command: {subcommand}")


def build_and_register_config(args: Namespace) -> AppConfig:
    output_dir = os.path.abspath(args.output_dir) if args.output_dir else None
    ollama_kwargs = {} if not args.provider_url else {"provider_url": args.provider_url}
    subcommand = args.command
    task_type = _subcommand_to_task_type(subcommand=subcommand)
    output_type = args.output_type
    ConfigSingleton.init(
        model=args.model,
        output_dir=output_dir,
        task_type=task_type,
        output_type=output_type,
        **ollama_kwargs,
    )

    return ConfigSingleton.config


def _subcommand_to_task_type(
    subcommand: str,
) -> type[Task]:
    match subcommand.strip().lower():
        case "github":
            return GithubTask
        case "local":
            return LocalTask
        case "usebench":
            if not USEBENCH_ENABLED or UseBenchTask is None:
                raise ArgumentTypeError(
                    "USEBench is not enabled. Set USEBENCH_ENABLED=true and install extras: uv sync --extra usebench"
                )
            return UseBenchTask
        case "swebench":
            return SWEbenchTask
        case _:
            raise ArgumentTypeError(
                f"Received unsupported subcommand {subcommand} - cannot parse to supported Task Types"
            )


def setup_loguru(console_log_level: str, log_file: str | None) -> None:
    logger.remove()
    fmt = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <6}</level> | <cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>"
    logger.add(sys.stderr, level=console_log_level.upper(), format=fmt)
    if log_file:
        logger.add(log_file, level="DEBUG", format=fmt)
    logger.info(
        f"Loguru initialized: console={console_log_level.upper()}, file={'enabled @ DEBUG level' if log_file else 'disabled'}"
    )


def parse_output_type(value: str) -> Literal[Answer, CodeChange, Action]:
    if not value:
        raise ArgumentTypeError("Received None for parsing output type")
    match value.strip().lower():
        case "answer":
            return Answer
        case "codechange":
            return CodeChange
        case "action":
            return Action
        case _:
            raise ArgumentTypeError(f"Invalid output type: {value}")


def main():
    args, subparser_dest_attr_name = parse_args()
    setup_loguru(console_log_level=args.log_level, log_file=args.log_file)
    build_and_register_config(args)
    handle_command(args, subparser_dest_attr_name)


if __name__ == "__main__":
    main()
