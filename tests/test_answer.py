from pathlib import Path

import pytest

from docqa_rag.answer import DONT_KNOW, SYSTEM_PROMPT, build_prompt
from docqa_rag.store import SearchResult


def test_build_prompt_orders_documents_and_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    results = [
        SearchResult(
            score=0.9,
            source=str(tmp_path / "knowledge" / "pricing.md"),
            heading_path="Pricing > Enterprise",
            text="Enterprise costs 10.",
        ),
        SearchResult(
            score=0.5,
            source=str(tmp_path / "knowledge" / "intro.md"),
            heading_path="",
            text="Hello.",
        ),
    ]

    assert build_prompt("How much?", results) == (
        "<documents>\n"
        '<document source="knowledge/pricing.md" section="Pricing > Enterprise">\n'
        "Enterprise costs 10.\n"
        "</document>\n"
        '<document source="knowledge/intro.md">\n'
        "Hello.\n"
        "</document>\n"
        "</documents>\n"
        "\n"
        "Question: How much?"
    )
    assert DONT_KNOW in SYSTEM_PROMPT
