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

## Usage

Put `.md` files in `knowledge/` (subfolders are searched too) and run:

```sh
docqa ingest [--rebuild]
```

The index lives in `.docqa/` and mirrors the folder: new and changed files are
embedded, unchanged files are skipped, and deleted files are removed from the
index. Use `--rebuild` to re-embed everything. Add `--verbose` to see
tracebacks on errors.

```sh
docqa search "<query>" [--top-k N]
```

Prints the closest chunks (default 5) with scores and sources. It makes no LLM
call and needs `docqa ingest` to have run first.

## Development

```sh
uv run ruff check
uv run ruff format --check
uv run mypy src tests
uv run pytest
```
