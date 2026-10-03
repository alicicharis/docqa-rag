from pathlib import Path

import pytest

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
