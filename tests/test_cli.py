import pytest

from docqa_rag.cli import main


def test_help_exits_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["docqa", "--help"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
