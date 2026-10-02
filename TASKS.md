# Tasks

Ordered by build sequence.

## 1. Package scaffold - to do

**What:** The project is an installable `src/` package with a `docqa` command, and the lint, type and test checks run clean on it.

**Design:** [Stack](DESIGN.md#stack), [Layout](DESIGN.md#layout)

## 2. Document ingestion - to do

**What:** `docqa ingest <path>` indexes markdown files into the local index. Re-running it skips unchanged files and replaces changed ones, and a missing API key fails with one clear message.

**Design:** [Configuration](DESIGN.md#configuration), [Chunking](DESIGN.md#chunking), [Embeddings](DESIGN.md#embeddings), [Vector store](DESIGN.md#vector-store), [Ingest](DESIGN.md#ingest), [Errors and output](DESIGN.md#errors-and-output), [Testing](DESIGN.md#testing)

## 3. Semantic search - to do

**What:** `docqa search "<query>"` prints the most similar chunks with their scores and sources, without calling an LLM.

**Design:** [Search](DESIGN.md#search), [Vector store](DESIGN.md#vector-store), [Errors and output](DESIGN.md#errors-and-output)

## 4. Question answering - to do

**What:** `docqa ask "<question>"` answers from the indexed documents, and says it doesn't know when they don't contain the answer.

**Design:** [Ask](DESIGN.md#ask), [Configuration](DESIGN.md#configuration), [Errors and output](DESIGN.md#errors-and-output)

## 5. Evals - backlog

**What:** A repeatable way to measure retrieval and answer quality.

**Open:**

- Everything: dataset, metrics, how it runs. To be discussed.
- Whether `ask` should get a similarity threshold, calibrated from eval results.

## 6. Hybrid search - backlog

**What:** Retrieval combines semantic search with BM25 keyword search and reranks the merged results.

**Open:**

- BM25 implementation and where its index lives.
- How semantic and BM25 results are fused.
- Which reranker to use.

## 7. Citations - backlog

**What:** Answers point back to the source documents and sections they came from.

**Open:**

- Citation format, and how sources are shown in `ask` output.
