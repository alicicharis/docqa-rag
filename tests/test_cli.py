from pathlib import Path

import pytest
from chromadb.api.shared_system_client import SharedSystemClient

from docqa_rag import store
from docqa_rag.chunking import Chunk
from docqa_rag.cli import main


def test_help_exits_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["docqa", "--help"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0


def test_ingest_without_api_key_fails_before_touching_index(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("sys.argv", ["docqa", "ingest"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert "OPENAI_API_KEY" in capsys.readouterr().err
    assert not (tmp_path / ".docqa").exists()


def test_search_prints_nearest_chunk(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    SharedSystemClient.clear_system_cache()
    source = str((tmp_path / "knowledge" / "a.md").resolve())
    chunks = [
        Chunk(text="line one\nline two", heading_path="Pricing > Enterprise"),
        Chunk(text="other", heading_path="Other"),
    ]
    store.add_chunks(
        store.open_collection(), source, "h", chunks, [[1.0, 0.0], [0.0, 1.0]]
    )
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.setattr("docqa_rag.embeddings.embed", lambda texts: [[1.0, 0.0]])
    monkeypatch.setattr("sys.argv", ["docqa", "search", "q", "--top-k", "1"])

    main()

    assert capsys.readouterr().out == (
        "[1] 1.000  knowledge/a.md\n"
        "    Pricing > Enterprise\n"
        "    line one\n"
        "    line two\n"
    )


def test_ask_prints_answer_from_retrieved_chunks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    SharedSystemClient.clear_system_cache()
    source = str((tmp_path / "knowledge" / "a.md").resolve())
    chunks = [
        Chunk(text="near", heading_path="A"),
        Chunk(text="far", heading_path="B"),
    ]
    store.add_chunks(
        store.open_collection(), source, "h", chunks, [[1.0, 0.0], [0.0, 1.0]]
    )
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    monkeypatch.setattr("docqa_rag.embeddings.embed", lambda texts: [[1.0, 0.0]])
    calls: list[tuple[str, list[store.SearchResult]]] = []

    def fake_generate(question: str, results: list[store.SearchResult]) -> str:
        calls.append((question, results))
        return "the answer"

    monkeypatch.setattr("docqa_rag.answer.generate", fake_generate)
    monkeypatch.setattr("sys.argv", ["docqa", "ask", "q", "--top-k", "1"])

    main()

    assert capsys.readouterr().out == "the answer\n"
    assert len(calls) == 1
    assert calls[0][0] == "q"
    assert [r.text for r in calls[0][1]] == ["near"]


def test_ask_without_keys_names_both(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("sys.argv", ["docqa", "ask", "q"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "OPENAI_API_KEY" in err
    assert "ANTHROPIC_API_KEY" in err
    assert not (tmp_path / ".docqa").exists()
