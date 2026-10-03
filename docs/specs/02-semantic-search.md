# Semantic Search

## Why

**Backlog item:** Item 3: Semantic search - see `TASKS.md`

The index exists but nothing reads it yet. `search` is the retrieval debugging tool, and `ask` (item 4) retrieves chunks the same way, so it has to come first.

## What

`docqa search "<query>" [--top-k N]` embeds the query, takes the top-k most similar chunks from `./.docqa`, and prints each one with its score, source, heading path and text. It makes no LLM call.

A missing `OPENAI_API_KEY` exits 1 with one message. A missing or empty index exits 1 with a message to run `docqa ingest` first, and does so without creating `.docqa/` and without calling the embedding API.

Done when both tasks pass their verify steps and `docqa search` returns sensible results over the repo's own `knowledge/` folder.

## Context

**Relevant files:**

- `DESIGN.md` - sections Search, Vector store, Errors and output, Testing. Settled; follow them exactly.
- `src/docqa_rag/store.py` - Chroma access. Gains the query side.
- `src/docqa_rag/config.py` - constants. Gains `TOP_K`.
- `src/docqa_rag/cli.py` - gains the `search` subcommand; `ingest` and the error handler already exist.
- `src/docqa_rag/embeddings.py` - `embed(texts) -> list[list[float]]`, reused for the query. Unchanged.
- `tests/test_ingest.py` - shows the temp-dir Chroma fixture (`monkeypatch.chdir` + `SharedSystemClient.clear_system_cache()`). Reuse the same pattern.
- `tests/test_cli.py` - existing CLI tests; must keep passing.
- `README.md` - gains `search` usage.

**Patterns to follow:**

- Thin, fully typed functions over Chroma in `store.py`, like `stored_hash` and `stored_sources`. Must pass `mypy --strict`, with no `Any`.
- `cli.py` handlers look like `_run_ingest`: `require_env(...)` first, then the work, then `print`.
- Tests are plain pytest functions using `monkeypatch`/`tmp_path`.

**Key decisions already made (from `DESIGN.md`):**

- `docqa search "<query>" [--top-k N]`, default top-k 5, defined as a constant in `config.py`. No LLM call.
- `search` requires only `OPENAI_API_KEY`, checked before any work (`require_env`).
- Query vectors come from the same `embeddings.embed` (`text-embedding-3-small`). Chroma embedding functions are never used.
- One collection `docs` in `./.docqa`, cosine space. Score = `1 - distance`.
- Output is plain text per result: score, source, heading path, chunk text.
- A missing or empty index exits 1 with a message to run `docqa ingest` first.
- Errors: one line on stderr, exit 1, traceback only with `--verbose`. No custom retries.
- Tests make no live API calls. The ranking test checks that the fake embedder's nearest chunk comes first.

**Settled in this spec (details `DESIGN.md` leaves open):**

- No new module. The query side goes in `store.py`. `cli.py` embeds the query and passes the vector to the store. Item 4 will reuse the same two calls.
- `store.existing_collection() -> Collection` opens the index for reading:
  - If `INDEX_DIR` isn't a directory, raise before constructing `PersistentClient`, because constructing it creates the directory.
  - If the `docs` collection doesn't exist or `count() == 0`, raise.
  - In every case, raise `LookupError("no documents indexed - run docqa ingest first")`.
  - Open with `client.get_collection(COLLECTION, embedding_function=None)`.
- Order in the command: `require_env`, then `existing_collection()`, then embed the query, then query. A missing index never costs an API call.
- The query text is embedded as is, with no heading prefix: `embed([query])[0]`.
- `store.SearchResult` is a frozen dataclass `(score: float, source: str, heading_path: str, text: str)`. `store.query(collection, embedding, top_k) -> list[SearchResult]` calls `collection.query(query_embeddings=[embedding], n_results=top_k, include=["documents", "metadatas", "distances"])` and returns results in Chroma's order (best first). If `top_k` is larger than the collection, Chroma returns fewer results. That's fine.
- `--top-k` must be an integer >= 1. Anything else is an argparse error (exit 2, argparse's usage message), via a small `type=` function.
- Output format, per result, with one blank line between results:

  ```
  [1] 0.812  knowledge/pricing.md
      Pricing > Enterprise
      <chunk text, every line indented 4 spaces>
  ```

  - Rank starts at 1. The score is formatted `f"{score:.3f}"`.
  - The source is printed as `os.path.relpath(source)`, which is relative to cwd.
  - The heading path line is omitted when the path is empty.
  - Indent the chunk text with `textwrap.indent(text, "    ")`. Blank lines inside a chunk stay unindented, which is fine, because the `[n]` header lines still mark where each result starts.

- `--verbose` comes from the existing shared `common` parent parser.

## Constraints

**Must:**

- Pass `ruff check`, `ruff format --check`, `mypy src tests` (strict), `pytest`.
- Validate env before touching the index. Check the index before calling the embedding API.
- Keep SDK calls behind `embeddings.embed` and the `store.py` functions. No test makes a live API call.

**Must not:**

- Add dependencies or a new module.
- Use RAG/LLM frameworks or any Chroma embedding function.
- Add a similarity threshold, any flag beyond `--top-k` and `--verbose`, or JSON output.
- Change `ingest` behavior or refactor the existing ingest code.
- Modify `DESIGN.md`, `TASKS.md` or `AGENTS.md`.

**Out of scope:**

- `ask`, `answer.py` and `ANTHROPIC_API_KEY` (item 4).
- Hybrid search, reranking, evals (items 5 and 6).

## Tasks

### T1: Store query side

**Do:**

- `config.py`: add `TOP_K = 5`.
- `store.py`: add `SearchResult`, `existing_collection()` and `query(...)` as settled above. Read `heading_path` and `source` from metadata with the same `isinstance(..., str)` narrowing style the existing functions use.
- `tests/test_store.py` (new), using the temp-dir fixture pattern from `tests/test_ingest.py`:
  - Ranking: `add_chunks` three chunks with handcrafted vectors (e.g. `[1, 0, 0]`, `[0.7, 0.7, 0]`, `[0, 1, 0]`), query with `[1, 0, 0]` and `top_k=2`. Expect the two nearest in order, the first scoring `pytest.approx(1.0)`, with source, heading path and text carried through.
  - No `.docqa`: `existing_collection()` raises `LookupError` matching `run docqa ingest first`, and `.docqa` still doesn't exist afterwards.
  - Empty collection (`store.open_collection()` then nothing added): `existing_collection()` raises the same error.

**Files:** `src/docqa_rag/config.py`, `src/docqa_rag/store.py`, `tests/test_store.py`

**Verify:** `uv run pytest tests/test_store.py && uv run mypy src tests && uv run ruff check && uv run ruff format --check`

### T2: Search command

**Do:**

- `cli.py`:
  - Add a `search` subparser with `parents=[common]`, a positional `query`, and `--top-k` (default `TOP_K`, a `type=` function that rejects values < 1).
  - Add `_run_search(args)`: `require_env("OPENAI_API_KEY")`, `collection = store.existing_collection()`, `vector = embeddings.embed([args.query])[0]`, then print `store.query(collection, vector, args.top_k)` in the settled format.
  - Dispatch: no subcommand still prints help. `ingest` and `search` go to their handlers inside the existing `try`/`except`. Keep the typing explicit with `if`/`elif`, not a callable stored on the Namespace.
- `README.md`: in Usage, add `docqa search "<query>" [--top-k N]`. Say that it prints the closest chunks with scores and sources, makes no LLM call, and needs `docqa ingest` to have run first.
- `tests/test_cli.py`: add one test.
  - Setup: temp-dir Chroma, chunks added with `store.add_chunks` under the source `str((tmp_path / "knowledge" / "a.md").resolve())` using known vectors. Resolve the path because on macOS `tmp_path` sits behind the `/var` symlink, and an unresolved path would make `relpath` print `../..` segments. Set `OPENAI_API_KEY` to a dummy value and monkeypatch `docqa_rag.embeddings.embed` to return a fixed vector.
  - Run `docqa search "q" --top-k 1`.
  - Assert stdout is exactly the expected block for the nearest chunk: the `[1] 1.000  knowledge/...` header, the heading path line and the indented text.

**Files:** `src/docqa_rag/cli.py`, `README.md`, `tests/test_cli.py`

**Verify:** `uv run pytest && uv run mypy src tests && uv run ruff check && uv run ruff format --check`

## Done

- [ ] `uv run ruff check && uv run ruff format --check && uv run mypy src tests && uv run pytest` passes.
- [ ] Manual, with `OPENAI_API_KEY` in `.env`, after `docqa ingest` in the repo root: `docqa search "how much does it cost"` prints 5 results from `knowledge/pricing.md`-like sources, best first, with scores between 0 and 1.
- [ ] Manual: `docqa search "pricing" --top-k 2` prints 2 results. `docqa search "x" --top-k 0` prints an argparse usage error, and `echo $?` is `2`.
- [ ] Manual: in an empty scratch dir with the key set, `docqa search "x"` prints `docqa: no documents indexed - run docqa ingest first`, exits 1, and leaves no `.docqa/` behind.
- [ ] Manual: with the key unset and no `.env`, `docqa search "x"` prints one line naming `OPENAI_API_KEY` and exits 1.
- [ ] No regressions: `docqa --help` exits 0. `docqa ingest` behaves as before.
