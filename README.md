

```
# install dependencies, including usebench
uv sync

# usebench migration (you can specify a place to store the dataset)
uv run usebench-migration ./data
```


## Docker

Build image with just the agent:

```
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519

DOCKER_BUILDKIT=1 docker build --ssh default -t useagent .
```

Build image on top of existing image (useful when running on benchmarks):
```
DOCKER_BUILDKIT=1 docker build --build-arg BASE_IMAGE=usebench.sweb.eval.x86_64.django__django-10914 --ssh default -t useagent .
```


## Run

Run agent in the container. Assuming at path `/useagent`:

```
export GEMINI_API_KEY=...
PYTHONPATH=. uv run python app/main.py usebench --task-id swe_django__django-10914 --output-dir /output
```