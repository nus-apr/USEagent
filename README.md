

```
# install dependencies, including usebench
uv sync

# usebench migration (you can specify a place to store the dataset)
uv run usebench-migration ./data
```


## Docker


```
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519

DOCKER_BUILDKIT=1 docker build --ssh default -t useagent .
```