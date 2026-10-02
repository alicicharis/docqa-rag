# docqa-rag

A Python CLI (`docqa`) for question answering over local markdown documents. It ingests `.md` files into a local ChromaDB index using OpenAI embeddings, retrieves chunks by cosine similarity, and answers questions with Claude Sonnet. It's built for a single developer working in their own project directory, without RAG frameworks. It's ready to ship when `docqa ingest`, `docqa search` and `docqa ask` work end to end on a folder of markdown files and the checks (ruff, mypy, pytest) pass.

- Read `DESIGN.md` before writing code. Its decisions are settled; if work seems to need a different one, raise it with the user instead of deviating.
- `TASKS.md` lists what to build, in order.
