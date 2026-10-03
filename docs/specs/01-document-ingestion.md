# Document Ingestion

## Why

**Backlog item:** Item 2: Document ingestion - see `TASKS.md`

`search` and `ask` both read from the local index, so nothing else works until markdown files can be chunked, embedded and stored. This is the first command with real behavior.

## What

`docqa ingest [--rebuild]` indexes every `.md` file under `./knowledge/` into `./.docqa`, so the index mirrors that folder:

- Unchanged files are skipped without an embedding call.
- Changed files have their chunks replaced.
- Files removed from the folder have their chunks removed.
- `--rebuild` empties the index first.

A missing `OPENAI_API_KEY` exits 1 with one message before any work happens. On success the command prints one summary line, e.g. `12 files: 9 indexed (214 chunks), 3 unchanged, 1 removed`.

Done when the three tasks below pass their verify steps and `docqa ingest` works on a real `knowledge/` folder.

## Context

**Relevant files:**

- `DESIGN.md` - sections Configuration, Chunking, Embeddings, Vector store, Ingest, Errors and output, Testing. Settled; follow them exactly.
- `src/docqa_rag/cli.py` - argparse entry point, currently prints help only. Gains the `ingest` subcommand and error handling.
- `tests/test_cli.py` - existing CLI test; must keep passing.
- `README.md` - gains `ingest` usage.
- `pyproject.toml` - all runtime deps (`openai`, `chromadb`, `tiktoken`, `python-dotenv`) are already declared.

New modules (one responsibility each, per `DESIGN.md#layout`): `config.py`, `chunking.py`, `embeddings.py`, `store.py`, `ingest.py`.

**Patterns to follow:**

- Fully typed code that passes `mypy --strict`. No `Any`.
- Tests are plain pytest functions with `monkeypatch`/`tmp_path`, like `tests/test_cli.py`.

**Key decisions already made (from `DESIGN.md`):**

- `.env` is loaded with `load_dotenv(find_dotenv(usecwd=True))`. Env validation is a presence check (set and non-empty), with no live API call. `ingest` requires only `OPENAI_API_KEY`. The single error lists every missing variable. Exit 1.
- Model names, chunk sizes and the index and knowledge folder locations are module constants in `config.py`. No config file, no flags beyond `--rebuild` and `--verbose`.
- Chunking: tiktoken `cl100k_base`. Strip YAML front matter. Split on headings (all levels), pack whole paragraphs up to 500 tokens. Only a paragraph over budget is hard-split, by tokens with 50-token overlap, and overlap never crosses a heading. A fenced code block is never split unless it alone exceeds the budget. Heading path is joined with `>` (`Guide > Install > macOS`). Embedded text = heading path + chunk text.
- Embeddings: `text-embedding-3-small` via the OpenAI SDK. Batches stay within 2048 inputs and 300k total tokens per request. Chroma embedding functions are never used.
- Store: `chromadb.PersistentClient(path="./.docqa")` relative to cwd. One collection `docs`, created with `configuration={"hnsw": {"space": "cosine"}}` and `embedding_function=None`. Chunk ID `{source}#{chunk_index}`. Metadata: `source` (absolute resolved path), `content_hash` (hash of the whole file), `heading_path`, `chunk_index`.
- Ingest: `docqa ingest [--rebuild]` has no path argument and always ingests `./knowledge/` (relative to cwd), searched recursively for `.md` files. Other extensions are ignored. A missing folder is an error and is never created automatically.
- Ingest per file: unchanged hash → skip, no embed. Changed → delete all chunks for that `source`, then chunk, embed, add. New → chunk, embed, add. Then every indexed `source` no longer in the folder has its chunks deleted. No progress bar.
- Errors: no custom retries. Any failure prints one line to stderr and exits 1; traceback only with `--verbose`.

**Settled in this spec (details `DESIGN.md` leaves open):**

- Front matter: only when line 1 is exactly `---`; it ends at the next line that is `---` or `...`. Without a closing line, nothing is stripped.
- Headings: ATX only (`#` to `######` followed by a space), and only outside fenced code blocks. The heading line is not part of the chunk text; it lives in the heading path. Text before the first heading has an empty heading path. A heading with no body produces no chunk.
- Paragraphs: blocks separated by blank lines. A fenced code block (from ` ``` ` or `~~~` to its matching closing fence) is one block, blank lines included.
- Packing: chunk text is its paragraphs joined with `\n\n`. The 500-token budget applies to the chunk text; the heading path is not counted.
- Oversized block (paragraph or code block over 500 tokens): flush the current pack, then emit token windows of 500 with a stride of 450 (50 overlap) as standalone chunks. The next paragraph starts a fresh pack.
- Embedded text: `f"{heading_path}\n\n{text}"`, or just `text` when the heading path is empty. Chroma's `documents` field stores the chunk text alone; `heading_path` is metadata.
- `content_hash`: SHA-256 hex of the file's bytes.
- Files are read as UTF-8 and processed in sorted path order. The match is the exact `.md` suffix.
- Each file is processed fully (delete, embed, add) before the next. This also keeps each Chroma `add` far below its max batch size.
- A file that yields no chunks (empty, or front matter only) is left out of the summary (not counted in files, indexed, chunks or unchanged) and makes no embedding call. If it had stored chunks before, they are deleted and it counts as removed.
- Summary line, exactly: `f"{files} files: {indexed} indexed ({chunks} chunks), {unchanged} unchanged, {removed} removed"`. No pluralization handling.
- If `./knowledge` doesn't exist or isn't a directory, the error is `folder not found: knowledge/ - create it and add .md files` (printed as `docqa: folder not found: ...`).
- An empty `knowledge/` is not an error: every indexed source is removed and the summary reports `0 files`.
- `--rebuild`: delete the `docs` collection if it exists, then recreate it with the same configuration. Every file then counts as indexed, and `removed` is 0.
- Error flow: modules raise ordinary exceptions with a one-line, user-readable message. `config.py` defines `ConfigError(Exception)` for the env check. `cli.py` catches `Exception`, prints `docqa: <message>` to stderr, and exits 1. With `--verbose` it prints the traceback first.
- `--verbose` lives on a shared argparse parent parser attached to each subcommand, so `docqa ingest --verbose` works and `search`/`ask` can reuse it later.
- `docqa` with no subcommand keeps printing help, as it does now.
- The embedder is a plain callable, `Embedder = Callable[[list[str]], list[list[float]]]`. `ingest` takes it as a parameter so tests can pass a fake.

## Constraints

**Must:**

- Pass `ruff check`, `ruff format --check`, `mypy src tests` (strict), `pytest`.
- Validate env before touching the filesystem or index.
- Keep SDK calls behind the thin functions in `embeddings.py` and `store.py`. No test makes a live API call.

**Must not:**

- Add dependencies.
- Use RAG/LLM frameworks or any Chroma embedding function.
- Add retries, progress output, flags or config beyond what's listed here.
- Modify `DESIGN.md`, `TASKS.md` or `AGENTS.md`.

**Out of scope:**

- `search` and `ask` subcommands, and the query side of the store (items 3 and 4). The ranking test from `DESIGN.md#testing` belongs to item 3.
- `ANTHROPIC_API_KEY` handling beyond what `require_env` generically supports.

## Tasks

### T1: Markdown chunker

**Do:**

- `config.py`: constants `TOKENIZER = "cl100k_base"`, `CHUNK_TOKENS = 500`, `CHUNK_OVERLAP = 50`.
- `chunking.py`: frozen dataclass `Chunk(text: str, heading_path: str)` and `chunk_markdown(markdown: str) -> list[Chunk]`, implementing the chunking rules above. Load the tiktoken encoding once at module level or with `functools.cache`.
- `tests/test_chunking.py`, one focused test per case: heading splits with correct nested heading paths (including a deeper heading followed by a shallower one), code block containing blank lines and a `#` line stays whole, oversized paragraph is hard-split into ≤500-token windows whose consecutive tokens overlap by exactly 50, overlap doesn't cross a heading, small paragraphs pack into one chunk until the budget, front matter stripped.

**Files:** `src/docqa_rag/config.py`, `src/docqa_rag/chunking.py`, `tests/test_chunking.py`

**Verify:** `uv run pytest tests/test_chunking.py && uv run mypy src tests && uv run ruff check && uv run ruff format --check`

Note: tiktoken downloads `cl100k_base` on first use and caches it, so the first test run needs network access.

### T2: Embeddings and store access

**Do:**

- `config.py`: add `EMBEDDING_MODEL = "text-embedding-3-small"`, `EMBED_MAX_INPUTS = 2048`, `EMBED_MAX_TOKENS = 300_000`, `INDEX_DIR = ".docqa"`, `COLLECTION = "docs"`.
- `embeddings.py`: `Embedder` type alias. `batch_texts(texts: list[str]) -> list[list[str]]` greedily groups texts in order without exceeding either limit (tokens counted with the same tiktoken encoding). `embed(texts: list[str]) -> list[list[float]]` creates `OpenAI()`, calls `client.embeddings.create(model=EMBEDDING_MODEL, input=batch)` per batch, and returns vectors in input order.
- `store.py`: thin functions over Chroma:
  - `open_collection(rebuild: bool = False) -> Collection` - `PersistentClient(path=INDEX_DIR)`; if `rebuild`, delete `docs` when it exists; then `get_or_create_collection` with cosine space and `embedding_function=None`.
  - `stored_hash(collection, source) -> str | None` - `content_hash` of any chunk with that `source`, or `None`.
  - `stored_sources(collection) -> set[str]` - every distinct `source` in the collection.
  - `delete_source(collection, source) -> None`.
  - `add_chunks(collection, source, content_hash, chunks, embeddings) -> None` - IDs `{source}#{i}`, documents = chunk text, metadata per the design.
- `tests/test_embeddings.py`: one test that `batch_texts` splits at 2048 inputs, and one that it splits before 300k tokens.

**Files:** `src/docqa_rag/config.py`, `src/docqa_rag/embeddings.py`, `src/docqa_rag/store.py`, `tests/test_embeddings.py`

**Verify:** `uv run pytest tests/test_embeddings.py && uv run mypy src tests && uv run ruff check && uv run ruff format --check`

### T3: Ingest command

**Do:**

- `config.py`: `KNOWLEDGE_DIR = "knowledge"`, `ConfigError(Exception)` and `require_env(*names: str) -> None`. `require_env` calls `load_dotenv(find_dotenv(usecwd=True))`, then raises `ConfigError` naming every missing or empty variable in one message, e.g. `missing environment variables: OPENAI_API_KEY (set them in the environment or a .env file)`.
- `ingest.py`: frozen dataclass `IngestSummary(files, indexed, chunks, unchanged, removed)` and `ingest(embed: Embedder, rebuild: bool = False) -> IngestSummary`. In order, it:
  1. Checks `KNOWLEDGE_DIR` is a directory, raising the folder-not-found error otherwise.
  2. Discovers `.md` files and opens the collection.
  3. Runs the unchanged/changed/new logic per file. Changed files are deleted before adding, so stale higher-index chunks don't survive.
  4. Deletes every stored source not among the discovered files.
- `cli.py`: `ingest` subcommand (`--rebuild`, no positional args) plus the shared `--verbose` parent. Call `require_env("OPENAI_API_KEY")` first, then `ingest(embeddings.embed, args.rebuild)`, then print the summary line. Wrap the dispatch in the error handling described above.
- `README.md`: a Usage section covering:
  - Put `.md` files in `knowledge/` and run `docqa ingest [--rebuild]`.
  - The index lives in `.docqa/` and mirrors the folder, including deletions.
  - Use `--rebuild` to re-embed everything.
- `tests/test_ingest.py`, against a temp-dir Chroma (`monkeypatch.chdir(tmp_path)`, files written to `tmp_path / "knowledge"`), with a fake deterministic embedder that records how many texts it was called with:
  - New files, including one in a subfolder, are indexed; the summary counts are correct.
  - Re-run with no changes: embedder not called, every file counted unchanged.
  - Changed file whose new version has fewer chunks: the old chunk IDs past the new count are gone, and the stored hash is updated.
  - File deleted from the folder: its chunks are gone and `removed` is 1.
  - `rebuild=True` on an unchanged folder: every file is re-embedded and counted indexed.
  - Missing `knowledge/`: raises with the folder-not-found message.
- `tests/test_cli.py`: add one test where `OPENAI_API_KEY` is unset (`monkeypatch.delenv`, cwd = empty `tmp_path`) and `docqa ingest` exits 1, stderr names `OPENAI_API_KEY`, and no `.docqa` directory was created.

**Files:** `src/docqa_rag/config.py`, `src/docqa_rag/ingest.py`, `src/docqa_rag/cli.py`, `README.md`, `tests/test_ingest.py`, `tests/test_cli.py`

**Verify:** `uv run pytest && uv run mypy src tests && uv run ruff check && uv run ruff format --check`

## Done

- [ ] `uv run ruff check && uv run ruff format --check && uv run mypy src tests && uv run pytest` passes.
- [ ] Manual, with `OPENAI_API_KEY` in `.env`, in a scratch dir with `.md` files in `knowledge/`: `docqa ingest` prints `N files: N indexed (M chunks), 0 unchanged, 0 removed`, and `.docqa/` exists.
- [ ] Manual: running it again prints `N files: 0 indexed (0 chunks), N unchanged, 0 removed`.
- [ ] Manual: edit one file, delete another, re-run → `1 indexed`, `1 removed`, the rest unchanged. `docqa ingest --rebuild` re-indexes everything.
- [ ] Manual: with the key unset and no `.env`, `docqa ingest` prints one line naming `OPENAI_API_KEY` and `echo $?` is `1`. In a dir with no `knowledge/` folder, `docqa ingest` prints the folder-not-found line with no traceback; adding `--verbose` shows the traceback.
- [ ] No regressions: `docqa --help` still exits 0.
