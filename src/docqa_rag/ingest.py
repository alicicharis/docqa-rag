import hashlib
from dataclasses import dataclass
from pathlib import Path

from docqa_rag import store
from docqa_rag.chunking import chunk_markdown
from docqa_rag.config import KNOWLEDGE_DIR
from docqa_rag.embeddings import Embedder


@dataclass(frozen=True)
class IngestSummary:
    files: int
    indexed: int
    chunks: int
    unchanged: int
    removed: int


def ingest(embed: Embedder, rebuild: bool = False) -> IngestSummary:
    folder = Path(KNOWLEDGE_DIR)
    if not folder.is_dir():
        raise FileNotFoundError(
            f"folder not found: {KNOWLEDGE_DIR}/ - create it and add .md files"
        )
    paths = sorted(p.resolve() for p in folder.rglob("*.md") if p.is_file())
    collection = store.open_collection(rebuild)

    indexed = chunk_total = unchanged = 0
    for path in paths:
        source = str(path)
        data = path.read_bytes()
        content_hash = hashlib.sha256(data).hexdigest()
        if store.stored_hash(collection, source) == content_hash:
            unchanged += 1
            continue
        try:
            markdown = data.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValueError(f"{source}: not valid UTF-8 ({e.reason})") from e
        store.delete_source(collection, source)
        chunks = chunk_markdown(markdown)
        if chunks:
            texts = [
                f"{c.heading_path}\n\n{c.text}" if c.heading_path else c.text
                for c in chunks
            ]
            store.add_chunks(collection, source, content_hash, chunks, embed(texts))
        indexed += 1
        chunk_total += len(chunks)

    current = {str(p) for p in paths}
    stale = store.stored_sources(collection) - current
    for source in stale:
        store.delete_source(collection, source)

    return IngestSummary(
        files=len(paths),
        indexed=indexed,
        chunks=chunk_total,
        unchanged=unchanged,
        removed=len(stale),
    )
