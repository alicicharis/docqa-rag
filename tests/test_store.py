from pathlib import Path

import pytest
from chromadb.api.shared_system_client import SharedSystemClient

from docqa_rag import store
from docqa_rag.chunking import Chunk


@pytest.fixture(autouse=True)
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    # Chroma caches clients by the relative index path, which is the same in every test.
    SharedSystemClient.clear_system_cache()
    return tmp_path


def test_query_returns_nearest_chunks_first() -> None:
    chunks = [
        Chunk(text="exact", heading_path="A > One"),
        Chunk(text="close", heading_path="A > Two"),
        Chunk(text="far", heading_path=""),
    ]
    vectors = [[1.0, 0.0, 0.0], [0.7, 0.7, 0.0], [0.0, 1.0, 0.0]]
    store.add_chunks(store.open_collection(), "/docs/a.md", "h", chunks, vectors)

    results = store.query(store.existing_collection(), [1.0, 0.0, 0.0], top_k=2)

    assert [r.text for r in results] == ["exact", "close"]
    assert results[0].score == pytest.approx(1.0)
    assert results[0].score > results[1].score
    assert results[0].source == "/docs/a.md"
    assert results[0].heading_path == "A > One"


def test_existing_collection_without_index_raises_and_creates_nothing(
    workdir: Path,
) -> None:
    with pytest.raises(LookupError, match="run docqa ingest first"):
        store.existing_collection()

    assert not (workdir / ".docqa").exists()


def test_existing_collection_empty_raises() -> None:
    store.open_collection()

    with pytest.raises(LookupError, match="run docqa ingest first"):
        store.existing_collection()
