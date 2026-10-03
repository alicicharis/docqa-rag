# Question Answering

## Why

**Backlog item:** Item 4: Question answering - see `TASKS.md`

`search` returns raw chunks. `ask` is the command the tool exists for: it turns those chunks into an answer, and it is the last piece before `docqa` is ready to ship (see `AGENTS.md`).

## What

`docqa ask "<question>" [--top-k N]` retrieves the top-k chunks the same way `search` does, sends them with the question to `claude-sonnet-5-5`, and prints only the answer text. When the chunks don't contain the answer, it prints `I don't know based on the indexed documents.`

A missing `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` exits 1 with one message that names every missing key. A missing or empty index exits 1 with the existing `run docqa ingest first` message, without calling either API.

Done when both tasks pass their verify steps and `docqa ask` answers questions over the repo's own `knowledge/` folder.

## Context

**Relevant files:**

- `DESIGN.md` - sections Ask, Configuration, Errors and output. Settled; follow them exactly.
- `src/docqa_rag/answer.py` (new) - the prompt and the Anthropic call. Listed in `DESIGN.md` → Layout.
- `src/docqa_rag/config.py` - constants and `require_env`. Gains the answer model constants.
- `src/docqa_rag/cli.py` - gains the `ask` subcommand. `_run_search`, `_positive_int` and the top-level error handler already exist and get reused.
- `src/docqa_rag/store.py` - `existing_collection()`, `query()` and `SearchResult`, reused as is.
- `src/docqa_rag/embeddings.py` - `embed(texts)`, reused as is.
- `tests/test_cli.py` - `test_search_prints_nearest_chunk` shows the temp-dir Chroma setup and how to fake `embed`. `test_ingest_without_api_key_fails_before_touching_index` shows the env-failure test.
- `README.md` - gains `ask` usage.

**Patterns to follow:**

- SDK calls sit behind one thin function, like `embeddings.embed`. The client is constructed inside the function (`OpenAI()` there, `Anthropic()` here), so it picks up the key that `require_env` loaded from `.env`.
- `cli.py` handlers look like `_run_search`: `require_env(...)` first, then the work, then `print`.
- Fully typed, passes `mypy --strict`, no `Any`. Tests are plain pytest functions using `monkeypatch`/`tmp_path`/`capsys`.

**Key decisions already made (from `DESIGN.md`):**

- `docqa ask "<question>" [--top-k N]`, default top-k from `config.TOP_K` (5). Retrieval is the same as `search`.
- Model `claude-sonnet-5-5`, `max_tokens` 1024, no streaming, via the `anthropic` SDK directly. No frameworks.
- There is no similarity threshold, and the LLM is always called, even on weak matches.
- The prompt restricts the answer to the provided context. If the context lacks the answer, the model says it doesn't know.
- Only the answer is printed. There are no sources, citations or scores.
- `ask` requires `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`. Validation is a presence check, done before any work, and one error lists every missing key.
- There are no custom retries. Errors print one line on stderr and exit 1, with a traceback only with `--verbose`. A missing or empty index exits 1 with a message to run `docqa ingest` first.

**Settled in this spec (details `DESIGN.md` leaves open):**

- `config.py` gains `ANSWER_MODEL = "claude-sonnet-5-5"` and `ANSWER_MAX_TOKENS = 1024`.
- `answer.py` exposes:
  - `DONT_KNOW = "I don't know based on the indexed documents."`
  - `SYSTEM_PROMPT`: a module constant. It says the model answers questions using only the documents in the user message, answers directly and concisely in plain text, and replies with exactly the `DONT_KNOW` sentence when the documents don't contain the answer. It is built from `DONT_KNOW` (f-string), so the two can't drift. It asks for no citations.
  - `build_prompt(question: str, results: list[SearchResult]) -> str`: a pure function. It puts the documents first and the question last, which suits long context:

    ```
    <documents>
    <document source="knowledge/pricing.md" section="Pricing > Enterprise">
    {chunk text}
    </document>
    ...
    </documents>

    Question: {question}
    ```

    - `source` is `os.path.relpath(r.source)`, the same as `search` prints. The `section` attribute is omitted when `heading_path` is empty.
    - Results stay in retrieval order (best first). Scores are not included.

  - `generate(question: str, results: list[SearchResult]) -> str` builds the prompt and calls `Anthropic().messages.create(model=ANSWER_MODEL, max_tokens=ANSWER_MAX_TOKENS, thinking={"type": "between_tools"}, system=SYSTEM_PROMPT, messages=[{"role": "user", "content": build_prompt(...)}])`:
    - `thinking={"type": "between_tools"}` turns thinking off on Sonnet 5.5. By default Sonnet 5.5 runs adaptive thinking, and that would spend the 1024-token budget before the answer. The model rejects `{"type": "disabled"}` with a 400, so `between_tools` is the only off switch. It is valid at the default effort, so don't set `output_config`.
    - If `response.stop_reason == "refusal"`, raise `RuntimeError("the model declined to answer")`. The CLI handler prints it as `docqa: the model declined to answer` and exits 1.
    - Otherwise return the `text` of every `type == "text"` block in `response.content`, joined with `""` and `.strip()`ped.

- The function is `generate`, not `answer`, so the call site reads `answer.generate(...)` and doesn't shadow the module name.
- `_run_ask` order: `require_env("OPENAI_API_KEY", "ANTHROPIC_API_KEY")`, then `store.existing_collection()`, then `embeddings.embed([args.question])[0]`, then `store.query(...)`, then `print(answer.generate(args.question, results))`. A missing key or index never costs an API call.
- `--top-k` reuses `_positive_int`: an integer >= 1, or an argparse error that exits 2.

## Constraints

**Must:**

- Pass `ruff check`, `ruff format --check`, `mypy src tests` (strict), `pytest`.
- Validate both keys before touching the index, and check the index before any API call.
- Keep the Anthropic call inside `answer.generate`. No test makes a live API call.

**Must not:**

- Add dependencies. `anthropic` is already in `pyproject.toml`.
- Add a similarity threshold, streaming, citations or sources in the output, or flags beyond `--top-k` and `--verbose`.
- Add custom retry logic, refusal fallbacks or a model fallback.
- Change `ingest` or `search` behavior, or refactor `store.py`/`embeddings.py`. A shared retrieval helper between `_run_search` and `_run_ask` isn't worth it for three lines. Write the calls out in both.
- Modify `DESIGN.md`, `TASKS.md` or `AGENTS.md`.

**Out of scope:**

- Evals and threshold calibration (item 5), hybrid search (item 6), citations (item 7).
- Conversation history or multi-turn `ask`.

## Tasks

### T1: Answer module

**Do:**

- `config.py`: add `ANSWER_MODEL` and `ANSWER_MAX_TOKENS` as settled above.
- `answer.py` (new): `DONT_KNOW`, `SYSTEM_PROMPT`, `build_prompt`, `generate` as settled above. Import `Anthropic` with `from anthropic import Anthropic`, the same way `embeddings.py` imports `OpenAI`.
- `tests/test_answer.py` (new), one test for `build_prompt`. Use two `SearchResult`s, one with an empty heading path, both under sources resolved under `tmp_path` with `monkeypatch.chdir(tmp_path)`. Assert:
  - the full output string exactly, which checks document order, the relpath `source`, the `section` attribute present on one and absent on the other, and `Question: ...` last;
  - `DONT_KNOW in SYSTEM_PROMPT`.
- Don't unit-test `generate`. It's a thin SDK wrapper, like `embeddings.embed`, and the manual checks in Done exercise it.

**Files:** `src/docqa_rag/config.py`, `src/docqa_rag/answer.py`, `tests/test_answer.py`

**Verify:** `uv run pytest tests/test_answer.py && uv run mypy src tests && uv run ruff check && uv run ruff format --check`

### T2: Ask command

**Do:**

- `cli.py`:
  - Import `answer` alongside `embeddings, store`.
  - Add an `ask` subparser (`parents=[common]`, help `answer a question from the indexed documents`) with a positional `question` and `--top-k` (the same `type=_positive_int`, default and help as `search`).
  - Add `_run_ask(args)` in the settled order.
  - Dispatch: add `"ask"` to the known commands and an `elif args.command == "ask":` branch inside the existing `try`.
- `README.md`: in Usage, after `search`, add `docqa ask "<question>" [--top-k N]`. Say that it answers from the closest chunks (default 5) with Claude, prints only the answer, says it doesn't know when the documents don't cover the question, and needs both keys and `docqa ingest` to have run first.
- `tests/test_cli.py`: add two tests.
  - `test_ask_prints_answer_from_retrieved_chunks`: set up chunks in a temp-dir Chroma the way `test_search_prints_nearest_chunk` does, set both keys to dummy values, fake `docqa_rag.embeddings.embed`, and monkeypatch `docqa_rag.answer.generate` with a function that records its arguments and returns `"the answer"`. Run `docqa ask "q" --top-k 1`. Assert stdout is `"the answer\n"`, and that the fake received question `"q"` and exactly one result, the nearest chunk's text.
  - `test_ask_without_keys_names_both`: in an empty `tmp_path` with both keys unset (`monkeypatch.delenv(..., raising=False)`), run `docqa ask "q"`. Expect exit 1, stderr containing both `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`, and no `.docqa` created.

**Files:** `src/docqa_rag/cli.py`, `README.md`, `tests/test_cli.py`

**Verify:** `uv run pytest && uv run mypy src tests && uv run ruff check && uv run ruff format --check`

## Done

- [ ] `uv run ruff check && uv run ruff format --check && uv run mypy src tests && uv run pytest` passes.
- [ ] Manual, with both keys in `.env`, after `docqa ingest` in the repo root: `docqa ask "<a question answered in knowledge/pricing.md>"` prints a short plain-text answer that matches the file, with no sources or scores.
- [ ] Manual: `docqa ask "What is the capital of France?"` prints `I don't know based on the indexed documents.`
- [ ] Manual: `docqa ask "x" --top-k 0` prints an argparse usage error, and `echo $?` is `2`.
- [ ] Manual: with `ANTHROPIC_API_KEY` removed from `.env` and the environment, `docqa ask "x"` prints one line naming `ANTHROPIC_API_KEY` and exits 1.
- [ ] Manual: in an empty scratch dir with both keys set, `docqa ask "x"` prints `docqa: no documents indexed - run docqa ingest first`, exits 1, and leaves no `.docqa/` behind.
- [ ] No regressions: `docqa --help` exits 0. `docqa ingest` and `docqa search` behave as before.
