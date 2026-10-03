import hashlib
from pathlib import Path

import pytest

from docqa_rag import store
from docqa_rag.ingest import ingest

SMALL = "# Title\n\nSome body text.\n"


class FakeEmbedder:
    def __init__(self) -> None:
        self.texts = 0

    def __call__(self, texts: list[str]) -> list[list[float]]:
        self.texts += len(texts)
        return [[float(len(t)), 1.0, 0.5] for t in texts]


@pytest.fixture
def knowledge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "knowledge"
    folder.mkdir()
    return folder


def test_new_files_are_indexed(knowledge: Path) -> None:
    (knowledge / "a.md").write_text(SMALL)
    (knowledge / "sub").mkdir()
    (knowledge / "sub" / "b.md").write_text(SMALL)
    (knowledge / "ignored.txt").write_text(SMALL)

    summary = ingest(FakeEmbedder())

    assert (summary.files, summary.indexed, summary.chunks) == (2, 2, 2)
    assert (summary.unchanged, summary.removed) == (0, 0)
    assert store.stored_sources(store.open_collection()) == {
        str((knowledge / "a.md").resolve()),
        str((knowledge / "sub" / "b.md").resolve()),
    }


def test_rerun_without_changes_skips_embedding(knowledge: Path) -> None:
    (knowledge / "a.md").write_text(SMALL)
    (knowledge / "b.md").write_text(SMALL)
    ingest(FakeEmbedder())

    embedder = FakeEmbedder()
    summary = ingest(embedder)

    assert embedder.texts == 0
    assert (summary.indexed, summary.unchanged) == (0, 2)


def test_changed_file_replaces_chunks(knowledge: Path) -> None:
    path = knowledge / "a.md"
    path.write_text("# One\n\nfirst\n\n# Two\n\nsecond\n\n# Three\n\nthird\n")
    ingest(FakeEmbedder())
    source = str(path.resolve())
    collection = store.open_collection()
    assert collection.count() == 3

    path.write_text("# One\n\nfirst changed\n")
    summary = ingest(FakeEmbedder())

    assert summary.indexed == 1
    assert collection.get()["ids"] == [f"{source}#0"]
    new_hash = store.stored_hash(collection, source)
    assert new_hash == hashlib.sha256(path.read_bytes()).hexdigest()


def test_deleted_file_is_removed(knowledge: Path) -> None:
    (knowledge / "a.md").write_text(SMALL)
    (knowledge / "b.md").write_text(SMALL)
    ingest(FakeEmbedder())

    (knowledge / "b.md").unlink()
    summary = ingest(FakeEmbedder())

    assert (summary.files, summary.removed) == (1, 1)
    assert store.stored_sources(store.open_collection()) == {
        str((knowledge / "a.md").resolve())
    }


def test_rebuild_reembeds_everything(knowledge: Path) -> None:
    (knowledge / "a.md").write_text(SMALL)
    (knowledge / "b.md").write_text(SMALL)
    ingest(FakeEmbedder())

    embedder = FakeEmbedder()
    summary = ingest(embedder, rebuild=True)

    assert embedder.texts == 2
    assert (summary.indexed, summary.unchanged, summary.removed) == (2, 0, 0)


def test_missing_knowledge_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError, match=r"folder not found: knowledge/"):
        ingest(FakeEmbedder())
