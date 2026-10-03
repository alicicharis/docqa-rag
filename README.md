# docqa-rag

`docqa` is a CLI for question answering over local markdown documents.

## Setup

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/).

Install the `docqa` command:

```sh
uv tool install .
```

Set these keys in your environment or in a `.env` file in the directory you run `docqa` from:

- `OPENAI_API_KEY` - used by all commands, for embeddings
- `ANTHROPIC_API_KEY` - used by `docqa ask`, for answers

## Development

```sh
uv run ruff check
uv run ruff format --check
uv run mypy src tests
uv run pytest
```
