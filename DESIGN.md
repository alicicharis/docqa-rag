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

- Evals live in `evals/`, outside the package. See [Evals](#evals).
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

## Evals

`uv run python -m evals.run`

- A dev script in `evals/`, not a `docqa` command. It isn't installed with the tool and pytest doesn't run it. It makes live OpenAI and Anthropic calls, so it needs both keys.
- It runs against the existing `./.docqa` index and never ingests. Run `docqa ingest` first when `knowledge/` has changed.
- Modules: `metrics.py` (pure retrieval metrics), `judge.py` (the judge's Anthropic call), `run.py` (loads the dataset, runs the questions, prints and saves results).

### Dataset

`evals/questions.json` is a list of cases: `{"question", "answer", "evidence"}`.

- `answer` is the reference answer, or `null` when the documents don't contain one (unanswerable).
- `evidence` lists the facts the answer needs, as groups of section keys. Each group is one fact, and any section in the group supplies it. Unanswerable cases have `[]`.
- A section key is `{source relative to cwd} > {heading_path}`, e.g. `knowledge/pricing.md > Quillbyte Pricing > Discounts`, or just the source when the heading path is empty. Labels use sections, not chunk IDs, because chunk IDs change whenever chunking does.

### Retrieval metrics

- Each question is embedded and queried once at top-k `config.TOP_K` (5), the same path as `ask`. A result matches a group when its section key is in that group.
- Over answerable cases, at k = 1, 3 and 5:
  - **hit@k:** at least one group is matched in the top k.
  - **recall@k:** every group is matched in the top k.
  - **MRR:** the mean of 1/rank of the first matching result, or 0 when none of the top 5 match.

### Answer grading

- `answer.generate` runs on the same retrieved results, so the eval measures exactly what `ask` would print.
- Unanswerable: correct only when the answer equals `answer.DONT_KNOW` exactly.
- Answerable: an answer equal to `DONT_KNOW` is a false refusal and counts as incorrect without a judge call. Any other answer goes to the judge.
- The judge is `claude-opus-5-5`, a different model from the answer model, so the answer model never grades its own output. It runs at effort `low` and returns structured JSON `{"correct": bool, "reason": str}`. An answer is correct when it states the reference's facts and contradicts none of them. Wording, format and extra correct detail don't matter.

### Output

- A per-question table, then each incorrect answer with the judge's reason, then a summary: the retrieval metrics, answer accuracy, unanswerable accuracy, the false refusal count, and the top-1 similarity score range for answerable vs unanswerable cases.
- Every run writes `evals/results/{timestamp}.json` (gitignored) with the models and top-k used, every question's details and the summary.
- Each question runs once. There are no repeats or concurrency.
- The top-1 scores are the input for a future `ask` similarity threshold. The eval only reports them and sets no threshold.
