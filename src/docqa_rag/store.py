from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.errors import NotFoundError

from docqa_rag.chunking import Chunk
from docqa_rag.config import COLLECTION, INDEX_DIR


def open_collection(rebuild: bool = False) -> Collection:
    client = chromadb.PersistentClient(path=INDEX_DIR)
    if rebuild and COLLECTION in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION)
    return client.get_or_create_collection(
        COLLECTION,
        configuration={"hnsw": {"space": "cosine"}},
        embedding_function=None,
    )


def stored_hash(collection: Collection, source: str) -> str | None:
    result = collection.get(where={"source": source}, limit=1, include=["metadatas"])
    metadatas = result["metadatas"]
    if not metadatas:
        return None
    value = metadatas[0]["content_hash"]
    return value if isinstance(value, str) else None


def stored_sources(collection: Collection) -> set[str]:
    metadatas = collection.get(include=["metadatas"])["metadatas"] or []
    return {m["source"] for m in metadatas if isinstance(m["source"], str)}


def delete_source(collection: Collection, source: str) -> None:
    collection.delete(where={"source": source})


def add_chunks(
    collection: Collection,
    source: str,
    content_hash: str,
    chunks: list[Chunk],
    embeddings: list[list[float]],
) -> None:
    if not chunks:
        return
    vectors: list[Sequence[float]] = list(embeddings)
    collection.add(
        ids=[f"{source}#{i}" for i in range(len(chunks))],
        embeddings=vectors,
        documents=[c.text for c in chunks],
        metadatas=[
            {
                "source": source,
                "content_hash": content_hash,
                "heading_path": c.heading_path,
                "chunk_index": i,
            }
            for i, c in enumerate(chunks)
        ],
    )


@dataclass(frozen=True)
class SearchResult:
    score: float
    source: str
    heading_path: str
    text: str


def existing_collection() -> Collection:
    error = LookupError("no documents indexed - run docqa ingest first")
    # PersistentClient creates the directory, so check before constructing it.
    if not Path(INDEX_DIR).is_dir():
        raise error
    client = chromadb.PersistentClient(path=INDEX_DIR)
    try:
        collection = client.get_collection(COLLECTION, embedding_function=None)
    except NotFoundError as exc:
        raise error from exc
    if collection.count() == 0:
        raise error
    return collection


def query(
    collection: Collection, embedding: list[float], top_k: int
) -> list[SearchResult]:
    vectors: list[Sequence[float]] = [embedding]
    result = collection.query(
        query_embeddings=vectors,
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    documents = (result["documents"] or [[]])[0]
    metadatas = (result["metadatas"] or [[]])[0]
    distances = (result["distances"] or [[]])[0]
    results: list[SearchResult] = []
    for text, metadata, distance in zip(documents, metadatas, distances, strict=True):
        source = metadata["source"]
        heading_path = metadata["heading_path"]
        results.append(
            SearchResult(
                score=1 - distance,
                source=source if isinstance(source, str) else "",
                heading_path=heading_path if isinstance(heading_path, str) else "",
                text=text,
            )
        )
    return results
