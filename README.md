# USEAgent

## Set up

It is **strongly recommended not to run USEagent outside of docker containers**, prefer to start a USEAgent Container and mount relevant files in as a copy.

Build **docker image** with just the agent:

```shell
DOCKER_BUILDKIT=1 docker build --build-arg USEBENCH_ENABLED=false -t useagent-turbo:dev .
```

Build image on top of existing image (useful when running on benchmarks, example script assumes you have a `my.project.to_work_on` image):

```shell
DOCKER_BUILDKIT=1 docker build --build-arg BASE_IMAGE=my.project.to_work_on --ssh default -t useagent-turbo:dev .
```

For working on USEBench, see [notes on usebench](./resources/USEBench-Instructions.md).
If you are in a sufficiently containerized environment, you may want to use USEagent directly:

[Install UV](https://docs.astral.sh/uv/getting-started/installation/)

```shell
uv sync
uv build
uv run <<args>>
```

## Run LOCAL

Example run in a (fresh) local folder:

```shell
mkdir ./useagent-turbo-tmp
echo "Hi, this is a simple file" > ./useagent-turbo-tmp/README.md

docker run --rm \
  --name useagent-turbo-test \
  -e GEMINI_API_KEY=YOUR_KEY_GOES_HERE \
  -v ./useagent-turbo-tmp:/input \
  useagent-turbo:dev \
  useagent local --model google-gla:gemini-2.0-flash --task-description 'write a shell file that prints a vegan tiramisu recipe' --output-dir /output --project-directory /input"
```

Inside the docker container, there will be a working-copy of your project created, so any files you mount in are *safe* and will remain unchanged.

## Run on Github Repository

Example will checkout the repository:

```shell

docker run --rm \
  --name useagent-turbo-test \
  -e GEMINI_API_KEY=YOUR_KEY_GOES_HERE \
  -v ./useagent-turbo-tmp-out:/output \
  useagent-turbo:dev \
  useagent github --model google-gla:gemini-2.0-flash --task-description 'write a shell file that prints a vegan tiramisu recipe' --repo-url https://github.com/octocat/Hello-World.git --output-dir /output"
```

## Run Other / Examples

There are more [example scripts](./scripts/) as well as [scripts to run on benchmarks](./scripts/experiments/).

They assume that the correct key (see below) are in a `.env` file and available in the runtime.

## CONFIGURATION

**Supported `--model`s:**

| Model                                | Required ENV        |
|--------------------------------------|---------------------|
| 'google-gla:gemini-2.0-flash'        | `GEMINI_API_KEY`    |
| 'openai:gpt-4o'                      | `OPENAI_API_KEY`    |
| 'anthropic:claude-3-5-sonnet-latest' | `ANTHROPIC_API_KEY` |

See more [at pydantic API Documentation](https://ai.pydantic.dev/models/)

## Licence / Terms of Agreement

Code within this project follows the [Apache 2.0 License](./LICENSE).

We further provide a local copy of the `gemma-3-4b-it` model, which comes with [terms of usage](./useagent/common/tokenizers/gemma-3-4b-it/TERMS_OF_USAGE.md).
Any usage or distribution must comply with them.

## Sources & Citation

A preprint is [available on arxiv](https://arxiv.org/abs/2506.14683).

For now, to cite please use:

```
@article{applis2025unified,
  title={Unified Software Engineering agent as AI Software Engineer},
  author={Applis, Leonhard and Zhang, Yuntong and Liang, Shanchao and Jiang, Nan and Tan, Lin and Roychoudhury, Abhik},
  journal={arXiv preprint arXiv:2506.14683},
  year={2025}
}
```
