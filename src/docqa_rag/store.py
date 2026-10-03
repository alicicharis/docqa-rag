from collections.abc import Sequence

import chromadb
from chromadb.api.models.Collection import Collection

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
