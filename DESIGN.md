# Design

## Scope

`docqa` is a local CLI that indexes markdown files and answers questions about them. It has three commands: `ingest`, `search`, `ask`.

Never:

- RAG or LLM frameworks (LangChain, LlamaIndex, etc.). Use the provider SDKs directly.
- A server, multiple users, or a remote Chroma instance.
- Multiple indexes or collections.

## Stack

- Python 3.13, managed with uv. `src/` layout, package `docqa_rag`, console script `docqa` (`docqa_rag.cli:main`).
- Distribution: local install only (`uv tool install .`).
- `anthropic` SDK for answers, `openai` SDK for embeddings.
- `chromadb` 1.x in embedded mode (`PersistentClient`). Collection names must be at least 3 characters.
- `tiktoken` for token counting.
- `python-dotenv` for `.env` loading. Config is hand-rolled; no `pydantic-settings`.
- CLI: stdlib `argparse`; no typer/click.
- Dev: `ruff` (lint + format), `mypy --strict`, `pytest`.

## Layout

One responsibility per module under `src/docqa_rag/`:

| Module          | Responsibility                                                           |
| --------------- | ------------------------------------------------------------------------ |
| `cli.py`        | argparse subcommands, `--verbose`, maps errors to exit codes             |
| `config.py`     | `.env` loading, per-command env validation, model and chunking constants |
| `chunking.py`   | markdown to chunks                                                       |
| `embeddings.py` | OpenAI embedding calls                                                   |
| `store.py`      | Chroma collection access                                                 |
| `ingest.py`     | file discovery, change detection, indexing                               |
| `answer.py`     | prompt and Anthropic call                                                |

- `main.py` from the `uv init` scaffold is removed.
- `.gitignore` includes `.docqa/` and `.env`.
- `README.md` covers setup (required env keys, install) and usage of the three commands.

## Configuration

- API keys come from `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`, set in the environment or in a `.env` file in the current working directory. Look the file up from the cwd (`find_dotenv(usecwd=True)`). The default search starts from the installed module's directory and would miss it.
- Each command validates its env before doing any work. Validation is a presence check: set and non-empty. It makes no live API call.
- Each command requires only the keys it uses:
  - `ingest`: `OPENAI_API_KEY`
  - `search`: `OPENAI_API_KEY`
  - `ask`: `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`
- On failure, print one error that lists every missing variable and exit 1.
- Models, chunk sizes and top-k default are module constants in `config.py`. There is no config file.

## Chunking

- Token-based, counted with tiktoken `cl100k_base`, the tokenizer `text-embedding-3-small` uses.
- Strip YAML front matter first.
- Split on markdown headings (all levels). Within a section, pack whole paragraphs up to a 500-token budget.
- Only a paragraph that alone exceeds the budget is hard-split by tokens, with a 50-token overlap. Overlap never crosses a heading boundary.
- A fenced code block is never split unless it alone exceeds the budget.
- Each chunk carries its heading path (`Guide > Install > macOS`). The embedded text is the heading path followed by the chunk text. This improves retrieval for short sections.

## Embeddings

- Model `text-embedding-3-small`, called through the OpenAI SDK.
- Embed in batches that stay within the API's per-request limits: 2048 inputs and 300k total tokens.
- Chroma's own embedding functions are never used: no default ONNX model, no `OpenAIEmbeddingFunction`.

## Vector store

- `chromadb.PersistentClient(path="./.docqa")`, resolved against the current working directory. There is no flag to override it.
- A single collection named `docs`, created with `configuration={"hnsw": {"space": "cosine"}}` and `embedding_function=None`. Chroma defaults to L2 distance, so `space` must be set.
- Similarity score = `1 - distance`.
- Chunk ID: `{source}#{chunk_index}`.
- Metadata per chunk: `source` (absolute resolved file path), `content_hash` (hash of the whole file), `heading_path`, `chunk_index`.

## Ingest

`docqa ingest [--rebuild]`

- Always ingests `./knowledge/`, resolved against the current working directory and searched recursively for `.md` files. Other extensions are ignored. There is no path argument or flag to change the folder.
- If `./knowledge/` doesn't exist, exit 1 with a message to create it and add `.md` files. It is never created automatically.
- For each file, compare its content hash with the stored `content_hash` for that `source`:
  - **Unchanged:** skip, with no embedding call.
  - **Changed:** delete all chunks for that `source`, then chunk, embed and add.
  - **New:** chunk, embed and add.
- **Removed:** every run deletes the chunks of any indexed `source` no longer in `./knowledge/`, so the index mirrors the folder.
- `--rebuild` empties the collection, then ingests. It's still needed after chunking or embedding changes, because file hashes don't change.
- On completion, print one summary line, e.g. `12 files: 9 indexed (214 chunks), 3 unchanged, 1 removed`. There is no progress bar.

## Search

`docqa search "<query>" [--top-k N]`

- Embeds the query and returns the top-k chunks from Chroma. Default top-k is 5.
- Makes no LLM call. It's the retrieval debugging tool and the future hook for evals.
- Output is plain text per result: score, source, heading path, chunk text.

## Ask

`docqa ask "<question>" [--top-k N]`

- Retrieves the top-k chunks the same way as `search`, sends them to `claude-sonnet-5-5`, and prints only the answer.
- There is no similarity threshold, and the LLM is always called. Any threshold would be uncalibrated until evals exist.
- The prompt restricts the answer to the provided context. If the context doesn't contain the answer, the model says it doesn't know.
- `max_tokens` is 1024. There is no streaming.
- No sources or citations are printed.

## Errors and output

- There is no custom retry logic. Rely on the SDKs' built-in retries.
- An API or runtime failure prints a one-line message to stderr and exits 1. A traceback is shown only with `--verbose`.
- `search` or `ask` on a missing or empty index exits 1 with a message to run `docqa ingest` first.

## Testing

- Focused unit tests, with no live API calls. SDK calls sit behind thin functions, so tests substitute a fake deterministic embedder.
- Chunker tests cover heading splits, code-block integrity, hard-split overlap, oversized paragraphs and front matter stripping.
- Store and ingest tests run against a temp-dir Chroma and cover upsert of changed files, hash-skip of unchanged files, removal of deleted files and `--rebuild`.
- Ranking tests check that the fake embedder's nearest chunk comes first.
