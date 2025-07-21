## Set up

[Install UV](https://docs.astral.sh/uv/getting-started/installation/)

```shell
# install dependencies, including usebench
uv sync

# usebench migration (you can specify a place to store the dataset)
uv run usebench-migration ./data
```

*Note*: USEBench is used to provide docker-images and texts - its docker-using APIs are not used.
The full work will be done on-top of the buggy usebench image.

## Docker

((the ssh key is necessary for now, due to usebench being private))
Build image with just the agent:

```shell
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519

DOCKER_BUILDKIT=1 docker build --ssh default -t useagent-turbo:dev .
```

Build image on top of existing image (useful when running on benchmarks):

```shell
DOCKER_BUILDKIT=1 docker build --build-arg BASE_IMAGE=usebench.sweb.eval.x86_64.django__django-10914 --ssh default -t useagent-turbo:dev .
```


### Development setup

Install app + dev dependencies:

```shell
uv sync --extra dev
```

If you want to add a new optional development dependency, do:

```shell
uv add --optional dev <package>
```

#### Before commiting changes

Install pre-commit hooks:

```shell
uv run pre-commit install
```

The pre-commit hooks will run before any commit is made.
Please make sure there is no pre-commit errors before code is pushed.

You can also run the pre-commit hooks manually with:

```shell
uv run pre-commit run --all-files
```



## Run

Start a container:

### USEBENCH

```shell
docker run -it --name useagent-turbo-test useagent-turbo:dev
```

Run agent in the container. Assuming at path `/useagent`:

```shell
export GEMINI_API_KEY=...
PYTHONPATH=. uv run python app/main.py usebench --model google-gla:gemini-2.0-flash --task-id swe_django__django-10914 --output-dir /output
```

```shell
export OPENAI_API_KEY=...
PYTHONPATH=. uv run python app/main.py usebench --model openai:gpt-4o --task-id swe_django__django-10914 --output-dir /output
```

Cleanup:
```shell
docker rm useagent-turbo-test && docker image rm useagent-turbo:dev
```

### LOCAL

Example run in a (fresh) local folder:

```shell
mkdir ./useagent-turbo-tmp
echo "Hi, this is a simple file" > ./useagent-turbo-tmp/README.md

docker run --rm \
  --name useagent-turbo-test \
  -e GEMINI_API_KEY=YOUR_KEY_GOES_HERE \
  -v ./useagent-turbo-tmp:/input \
  useagent-turbo:dev \
  /bin/bash -c "PYTHONPATH=. uv run python useagent/main.py local --model google-gla:gemini-2.0-flash --task-description 'write a shell file that prints a vegan tiramisu recipe' --output-dir /output --project-directory /input"
```

### Github

Example will checkout the repository:

```shell

docker run --rm \
  --name useagent-turbo-test \
  -e GEMINI_API_KEY=YOUR_KEY_GOES_HERE \
  -v ./useagent-turbo-tmp-out:/output \
  useagent-turbo:dev \
  /bin/bash -c "PYTHONPATH=. uv run python useagent/main.py github --model google-gla:gemini-2.0-flash --task-description 'write a shell file that prints a vegan tiramisu recipe' --repo-url https://github.com/octocat/Hello-World.git --output-dir /output"
```

### CONFIGURATION

**Supported `--model`s:**

| Model                                | Required ENV        |
|--------------------------------------|---------------------|
| 'google-gla:gemini-2.0-flash'        | `GEMINI_API_KEY`    |
| 'openai:gpt-4o'                      | `OPENAI_API_KEY`    |
| 'anthropic:claude-3-5-sonnet-latest' | `ANTHROPIC_API_KEY` |

See more [at pydantic API Documentation](https://ai.pydantic.dev/models/)

**Locally Hosted OLLama** _(assuming there is one running)_,
see more examples [at the pydantic OpenAI documentation](https://ai.pydantic.dev/models/openai/)

```shell
docker run -it --network=host --name useagent-turbo-test useagent-turbo:dev
```

*Linux*
```shell
PYTHONPATH=. uv run python app/main.py usebench --model llama3.3:70b  --provider-url http://localhost:11434/v1 --task-id swe_django__django-10914 --output-dir /output
```
*Macos*
```shell
PYTHONPATH=. uv run python app/main.py usebench --model llama3.2 --provider-url http://host.docker.internal:11434 --task-id swe_django__django-10914 --output-dir /output
```

## Tests

```shell
uv venv
source .venv/bin/activate  # On macOS/Linux
# OR on Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
uv run pytest tests
```