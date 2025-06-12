import os
from argparse import ArgumentParser, Namespace
from tempfile import mkdtemp

from app.config import AppConfig, ConfigSingleton
from app.tasks.usebench_task import UseBenchTask


def add_common_args(parser: ArgumentParser) -> None:
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Path to the directory that stores the run results.",
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
    from app import task_runner
    subcommand = getattr(args, subparser_dest_attr_name, None)
    if subcommand == "usebench":
        uid = args.task_id
        local_path = mkdtemp(prefix=f"acr_usebench_{uid}")
        usebench_task = UseBenchTask(
            uid=uid,
            project_path=local_path,
        )

        print(f"Running UseBench task with ID: {usebench_task.uid}")
        task_runner.run(usebench_task, args.output_dir)

    else:
        raise ValueError(f"Unknown command: {subcommand}")


def build_and_register_config(args: Namespace) -> AppConfig:
    output_dir = os.path.abspath(args.output_dir) if args.output_dir else None
    ollama_kwargs = {} if not args.provider_url else {"provider_url" : args.provider_url }
    ConfigSingleton.init(model=args.model, output_dir=output_dir, **ollama_kwargs)
    return ConfigSingleton.config


def main():
    args, subparser_dest_attr_name = parse_args()
    config = build_and_register_config(args)
    handle_command(args, subparser_dest_attr_name)

if __name__ == "__main__":
    main()