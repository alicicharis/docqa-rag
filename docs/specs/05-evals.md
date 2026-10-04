# Evals

## Why

**Backlog item:** Item 5: Evals - see `TASKS.md`

`ingest`, `search` and `ask` work, but there's no way to tell whether a change makes retrieval or answers better or worse. Hybrid search (item 6) and an `ask` similarity threshold both need a baseline to measure against.

## What

`uv run python -m evals.run`, run from the repo root, takes every case in `evals/questions.json` through the same retrieval and answer path as `docqa ask`. It then:

- scores retrieval against the labeled evidence sections (hit@k, recall@k, MRR),
- grades answers: an exact `DONT_KNOW` match for unanswerable cases, and an LLM judge for answerable ones,
- prints a per-question table, the failures and a summary,
- saves the full run to `evals/results/{timestamp}.json`.

Done when both tasks pass their verify steps and a run over the repo's `knowledge/` completes and prints the summary.

## Context

**Relevant files:**

- `DESIGN.md` - section Evals (settled; follow it exactly). Also Ask and Errors and output.
- `evals/questions.json` - the dataset. It already exists and is labeled. Don't edit it.
- `evals/__init__.py`, `evals/metrics.py`, `evals/judge.py`, `evals/run.py` (all new).
- `src/docqa_rag/answer.py` - `generate`, `DONT_KNOW`. Reused as is. `generate` shows the Anthropic call pattern to mirror in the judge.
- `src/docqa_rag/store.py` - `existing_collection`, `query`, `SearchResult`. Reused as is.
- `src/docqa_rag/embeddings.py` - `embed`. It batches internally, so embed all questions in one call.
- `src/docqa_rag/config.py` - `require_env`, `TOP_K`, `EMBEDDING_MODEL`, `ANSWER_MODEL`. Reused as is.
- `tests/test_eval_metrics.py` (new).
- `pyproject.toml`, `.gitignore`, `README.md`.

**Patterns to follow:**

- An SDK call sits behind one thin function, and the client is constructed inside it (`Anthropic()`), like `answer.generate`.
- Fully typed, passes `mypy --strict`, no `Any` annotations. Tests are plain pytest functions.
- Section keys are built with `os.path.relpath(result.source)`, the same as `search` prints.

**Key decisions already made (from `DESIGN.md` → Evals):**

- This is a dev script in `evals/`, not a `docqa` command, and not run by pytest. It needs both API keys and an existing index. It never ingests.
- Dataset case: `{"question": str, "answer": str | null, "evidence": list[list[str]]}`. A `null` answer means the case is unanswerable, with `evidence: []`. Each evidence group is one needed fact, and any section key in the group supplies it.
- Section key: `"{relpath(source)} > {heading_path}"`, or just `relpath(source)` when `heading_path` is empty.
- One query per question at `TOP_K`. The metrics, over answerable cases at k in (1, 3, `TOP_K`):
  - hit@k: any group matched.
  - recall@k: every group matched.
  - MRR: mean of 1/first matching rank, 0 when there's no match.
- Answers come from `answer.generate` over the same results.
  - Unanswerable: correct only when the answer `== DONT_KNOW`.
  - Answerable: `DONT_KNOW` counts as a false refusal (incorrect, no judge call). Anything else goes to the judge.
- Judge: `claude-opus-5-5`, effort `low`, structured JSON `{"correct": bool, "reason": str}`.
- Each question runs once, sequentially. The script reports top-1 scores and sets no threshold.

**Settled in this spec (details `DESIGN.md` leaves open):**

- `evals/__init__.py` is empty. It lets mypy and pytest see `evals` as a package (checked: without it, `mypy src tests evals` fails with "source file found twice").
- `pyproject.toml` `[tool.pytest.ini_options]` gains `pythonpath = ["."]` so tests can `from evals.metrics import ...`.
- `evals/metrics.py` (pure, no I/O):
  - `section_key(result: SearchResult) -> str`
  - `first_rank(keys: list[str], evidence: list[list[str]]) -> int | None`: the 1-based rank of the first key in any group, or `None`.
  - `hit(keys: list[str], evidence: list[list[str]], k: int) -> bool`
  - `recall(keys: list[str], evidence: list[list[str]], k: int) -> bool`
  - `keys` are the ranked section keys of one query's results. Callers only pass answerable cases, so there's no special case for empty evidence.
- `evals/judge.py`:
  - `JUDGE_MODEL = "claude-opus-5-5"`, `JUDGE_MAX_TOKENS = 4096`. Thinking is always on for Opus 5.5 and counts toward `max_tokens`, so 4096 leaves room at effort `low`.
  - `JUDGE_SYSTEM`: you grade an answer from a question answering system against a reference answer. The answer is correct when it states the reference's facts and contradicts none of them. Ignore wording, formatting and extra details that don't contradict the reference. Give a one-sentence reason.
  - `@dataclass(frozen=True) class Verdict: correct: bool; reason: str`
  - `grade(question: str, reference: str, answer: str) -> Verdict` calls:

    ```python
    Anthropic().messages.create(
        model=JUDGE_MODEL,
        max_tokens=JUDGE_MAX_TOKENS,
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": VERDICT_SCHEMA},
        },
        system=JUDGE_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    ```

    - Don't pass `thinking`. Opus 5.5 rejects disabling it, and leaving it out runs adaptive.
    - `VERDICT_SCHEMA` is an object with `correct` (boolean) and `reason` (string), both required, and `additionalProperties: False`.
    - `prompt` is `<question>{question}</question>\n<reference>{reference}</reference>\n<answer>{answer}</answer>`.
    - If `response.stop_reason != "end_turn"`, raise `RuntimeError(f"judge stopped with {response.stop_reason}")`.
    - Join the `text` blocks and `json.loads` the result into a variable annotated `object`. If it isn't a dict with a `bool` `correct` and a `str` `reason`, raise `RuntimeError` with the raw text.

- `evals/run.py`:
  - `class Case(TypedDict)` mirrors the dataset. Load it with `cases: list[Case] = json.loads(...)`, without runtime validation, because the file is ours.
  - Paths are `evals/questions.json` and `evals/results/`, relative to the cwd (the repo root, like `knowledge/` for `docqa`).
  - Order:
    1. `require_env("OPENAI_API_KEY", "ANTHROPIC_API_KEY")`.
    2. `store.existing_collection()`.
    3. One `embeddings.embed` call over all questions.
    4. For each case: `store.query(..., TOP_K)`, then `answer.generate`, then grading. Print the table row right away, so a run of about two minutes shows progress.
    5. Print the incorrect cases.
    6. Print the summary.
    7. Write the JSON.
  - There's no try/except. A missing key or index ends the run with the exception's traceback. It's a dev script.
  - The table. `type` is `A` (answerable) or `U` (unanswerable). `rank` is `first_rank`, or `-` for unanswerable cases and misses. `top1` is the score of result 1. `result` is `correct`, `incorrect` or `false refusal`. For unanswerable cases, `correct` means refused and `incorrect` means answered.

    ```
     #  type  rank   top1  result
     1  A        1  0.612  correct
     8  A        2  0.583  incorrect
    19  A        -  0.401  false refusal
    23  U        -  0.355  correct
    ```

  - Incorrect cases, after the table. Leave out the `judge:` line when no judge ran:

    ```
    Incorrect:
    [8] How much does extra Trailhead log ingestion cost?
        expected: $0.50 per GB.
        answer:   ...
        judge:    ...
    ```

  - Summary (ratios to 2 decimals, scores to 3):

    ```
    Retrieval (23 answerable)
      hit@1 0.83  hit@3 0.96  hit@5 1.00
      recall@1 0.70  recall@3 0.91  recall@5 0.96
      MRR 0.89
    Answers
      answerable 21/23 correct, 1 false refusal
      unanswerable 3/4 correct
    Top-1 score
      answerable    min 0.412  mean 0.587  max 0.731
      unanswerable  min 0.301  mean 0.355  max 0.402
    Saved evals/results/2026-10-04T14-03-11.json
    ```

  - The results file name comes from `datetime.now().strftime("%Y-%m-%dT%H-%M-%S")`. Create the directory if it's missing. JSON is `indent=2`:

    ```
    {
      "timestamp": "...",
      "config": {"top_k", "embedding_model", "answer_model", "judge_model"},
      "summary": {"hit@1", "hit@3", "hit@5", "recall@1", "recall@3", "recall@5", "mrr",
                  "answerable", "answerable_correct", "false_refusals",
                  "unanswerable", "unanswerable_correct",
                  "top1_answerable": {"min", "mean", "max"},
                  "top1_unanswerable": {"min", "mean", "max"}},
      "cases": [{"question", "expected", "evidence",
                 "retrieved": [{"section", "score"}],
                 "first_rank", "answer", "result", "judge_reason"}]
    }
    ```

    `judge_reason` is `null` when no judge ran.

  - End with `if __name__ == "__main__": main()`.

## Constraints

**Must:**

- Pass `ruff check`, `ruff format --check`, `mypy src tests evals` (strict), `pytest`.
- Use the same retrieval and answer functions `ask` uses, with no copies or variants.
- Keep the judge's Anthropic call inside `judge.grade`. No test makes a live API call.

**Must not:**

- Add dependencies. Use the `anthropic` SDK's raw JSON schema output, not pydantic.
- Change anything under `src/docqa_rag/`.
- Add CLI arguments to the script, concurrency, repeat runs, a similarity threshold, ingestion or custom retries.
- Edit `evals/questions.json`, `DESIGN.md`, `TASKS.md` or `AGENTS.md`.

**Out of scope:**

- The `ask` similarity threshold itself (decided after the first runs).
- Hybrid search (item 6), citations (item 7).
- Comparing runs or diffing results files.

## Tasks

### T1: Retrieval metrics

**Do:**

- `evals/__init__.py` (empty) and `evals/metrics.py`, as settled above.
- `pyproject.toml`: add `pythonpath = ["."]` to `[tool.pytest.ini_options]`.
- `tests/test_eval_metrics.py`, two tests:
  - `test_section_key`: with `monkeypatch.chdir(tmp_path)` and sources resolved under `tmp_path / "knowledge"`, a result with a heading path gives `knowledge/a.md > A > B`, and one with an empty heading path gives `knowledge/a.md`.
  - `test_retrieval_metrics`: keys `["x", "a2", "y", "b"]` and evidence `[["a1", "a2"], ["b"]]`. Assert:
    - `first_rank` is 2,
    - `hit` is False at k=1 and True at k=2,
    - `recall` is False at k=3 and True at k=4,
    - `first_rank(["x"], evidence)` is `None`.

**Files:** `evals/__init__.py`, `evals/metrics.py`, `pyproject.toml`, `tests/test_eval_metrics.py`

**Verify:** `uv run pytest tests/test_eval_metrics.py && uv run mypy src tests evals && uv run ruff check && uv run ruff format --check`

### T2: Judge and runner

**Do:**

- `evals/judge.py` and `evals/run.py`, as settled above.
- `.gitignore`: add `evals/results/` under the `# docqa` block.
- `README.md`:
  - Add an `## Evals` section before Development. Cover:
    - the command, run from the repo root after `docqa ingest`,
    - that it needs both keys and makes live API calls,
    - what it reports,
    - where results are saved,
    - the dataset format in two sentences.
  - In Development, change `uv run mypy src tests` to `uv run mypy src tests evals`.
- Don't unit-test `judge.grade` or `run.main`. They're live-API orchestration, and the manual check in Done exercises them.

**Files:** `evals/judge.py`, `evals/run.py`, `.gitignore`, `README.md`

**Verify:** `uv run pytest && uv run mypy src tests evals && uv run ruff check && uv run ruff format --check`

## Done

- [ ] `uv run ruff check && uv run ruff format --check && uv run mypy src tests evals && uv run pytest` passes.
- [ ] Manual, with both keys in `.env`, after `docqa ingest` in the repo root: `uv run python -m evals.run` prints 27 table rows as it goes, then the incorrect cases (if any), then the summary, and writes a JSON file under `evals/results/` that `git status` doesn't show.
- [ ] Manual: in the results JSON, every case has 5 `retrieved` entries, and `judge_reason` is set exactly for answerable cases that weren't refused.
- [ ] Manual: with `ANTHROPIC_API_KEY` removed from `.env` and the environment, the script fails before any API call, naming the key.
- [ ] No regressions: `docqa ingest`, `docqa search` and `docqa ask` behave as before.
