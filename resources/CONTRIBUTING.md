
## Development setup

Install app + dev dependencies:

```shell
uv sync --extra dev
```

If you want to add a new optional development dependency, do:

```shell
uv add --optional dev <package>
```

## Before commiting changes

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




## Tests

Run test with: 

```shell
uv sync --extra dev
uv run python -m pytest tests
```