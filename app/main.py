import os
from argparse import ArgumentParser, Namespace
from tempfile import mkdtemp

from app import config, task_runner
from app.tasks.usebench_task import UseBenchTask


def add_common_args(parser: ArgumentParser) -> None:
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Path to the directory that stores the run results.",
    )

    parser.add_argument(
        "--task-id", type=str, help="Unique identifier for the task run."
    )


def set_usebench_parser_args(parser: ArgumentParser) -> None:
    add_common_args(parser)

    parser.add_argument(
        "--task-list-file",
        type=str,
        help="Path to the file that contains all tasks ids to be run.",
    )


def parse_args():
    parser = ArgumentParser()

    subparser_dest_attr_name = "command"
    subparsers = parser.add_subparsers(dest=subparser_dest_attr_name)

    # TODO: add a common parser for all other kinds of tasks

    usebench_parser = subparsers.add_parser(
        "usebench", help="Run one or multiple usebench tasks."
    )
    set_usebench_parser_args(usebench_parser)

    return parser.parse_args(), subparser_dest_attr_name


def handle_command(args: Namespace, subparser_dest_attr_name: str) -> None:
    subcommand = getattr(args, subparser_dest_attr_name, None)
    if subcommand == "usebench":
        uid = args.task_id
        local_path = mkdtemp(prefix=f"acr_usebench_{uid}")
        usebench_task = UseBenchTask(
            uid=uid,
            project_path=local_path,
        )

        task_runner.run(usebench_task, args.output_dir)

    else:
        raise ValueError(f"Unknown command: {subcommand}")


def main():
    args, subparser_dest_attr_name = parse_args()

    config.output_dir = args.output_dir
    if config.output_dir is not None:
        config.output_dir = os.path.abspath(config.output_dir)

    handle_command(args, subparser_dest_attr_name)
