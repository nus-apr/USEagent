import os
from argparse import ArgumentParser, Namespace
from tempfile import mkdtemp
from pathlib import Path


from useagent.config import AppConfig, ConfigSingleton
from useagent.tasks.usebench_task import UseBenchTask
from useagent.tasks.local_task import LocalTask
from useagent.tasks.github_task import GithubTask
from useagent import task_runner

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

def set_local_parser_args(parser: ArgumentParser) -> None:
    add_common_args(parser)

    parser.add_argument('--project-directory', type=Path, help="Path to the folder containing the project to operate on.")

    task_group = parser.add_mutually_exclusive_group(required=True)
    task_group.add_argument('--task-description', type=str, help="Verbatim description of what should be done.")
    task_group.add_argument('--task-file', type=Path, help="A path to a markdown or text file containing the task.")

def set_github_parser_args(parser: ArgumentParser) -> None:
    add_common_args(parser)
    parser.add_argument('--repo-url', type=str, required=True, help="Git repository to clone (SSH or HTTPS).")
    parser.add_argument('--working-dir', type=Path, default=Path("/tmp/working_dir"), help="Target directory to clone into and work on (within Docker Container).")

    task_group = parser.add_mutually_exclusive_group(required=True)
    task_group.add_argument('--task-description', type=str, help="Verbatim description of what should be done.")
    task_group.add_argument('--task-file', type=Path, help="A path to a markdown or text file containing the task.")


def _get_task_description(args: Namespace) -> str:
    if args.task_description:
        return args.task_description
    if args.task_file and args.task_file.is_file():
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

    elif subcommand == "local":
        local_path = args.project_directory
        task_desc = _get_task_description(args)
        local_task = LocalTask(
            issue_statement=task_desc, 
            project_path=local_path)
        task_runner.run(local_task, args.output_dir)

    elif subcommand == "github":
        task_desc = _get_task_description(args)
        task = GithubTask(
            issue_statement=task_desc,
            repo_url=args.repo_url,
            working_dir=args.working_dir,
        )
        task_runner.run(task, args.output_dir)
        
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