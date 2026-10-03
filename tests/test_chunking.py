from itertools import pairwise

import tiktoken

from docqa_rag.chunking import Chunk, chunk_markdown
from docqa_rag.config import CHUNK_OVERLAP, CHUNK_TOKENS, TOKENIZER

enc = tiktoken.get_encoding(TOKENIZER)


def _words(n: int, prefix: str = "w") -> str:
    return " ".join(f"{prefix}{i}" for i in range(n))


def test_heading_splits_with_nested_paths() -> None:
    md = (
        "intro\n\n# Guide\n\ntop\n\n## Install\n\n### macOS\n\nbrew\n\n"
        "## Usage\n\nrun it\n\n# Other\n\nelse\n"
    )
    assert chunk_markdown(md) == [
        Chunk("intro", ""),
        Chunk("top", "Guide"),
        Chunk("brew", "Guide > Install > macOS"),
        Chunk("run it", "Guide > Usage"),
        Chunk("else", "Other"),
    ]


def test_code_block_with_blank_lines_and_hash_stays_whole() -> None:
    code = "```python\nx = 1\n\n# not a heading\ny = 2\n```"
    chunks = chunk_markdown(f"# Title\n\n{code}\n")
    assert chunks == [Chunk(code, "Title")]


def test_oversized_paragraph_hard_split_with_overlap() -> None:
    chunks = chunk_markdown("# T\n\n" + _words(1200))
    token_lists = [enc.encode(c.text) for c in chunks]
    assert len(chunks) > 2
    assert all(len(t) <= CHUNK_TOKENS for t in token_lists)
    for prev, nxt in pairwise(token_lists):
        assert prev[-CHUNK_OVERLAP:] == nxt[:CHUNK_OVERLAP]


def test_overlap_does_not_cross_heading() -> None:
    chunks = chunk_markdown(f"# A\n\n{_words(600, 'a')}\n\n# B\n\n{_words(600, 'b')}")
    a = [c for c in chunks if c.heading_path == "A"]
    b = [c for c in chunks if c.heading_path == "B"]
    assert a and b
    assert all("b0" not in c.text.split() for c in a)
    assert b[0].text.startswith("b0 ")


def test_small_paragraphs_pack_until_budget() -> None:
    para = _words(100)
    n = len(enc.encode(para))
    fits = (CHUNK_TOKENS - n) // (n + 1) + 1
    md = "\n\n".join([para] * (fits + 1))
    chunks = chunk_markdown(md)
    assert len(chunks) == 2
    assert chunks[0].text == "\n\n".join([para] * fits)
    assert chunks[1].text == para
    assert len(enc.encode(chunks[0].text)) <= CHUNK_TOKENS


def test_front_matter_stripped() -> None:
    chunks = chunk_markdown("---\ntitle: x\n---\n# H\n\nbody\n")
    assert chunks == [Chunk("body", "H")]


def test_code_block_adjacent_to_text_is_its_own_block() -> None:
    code = "```\ncode\n```"
    chunks = chunk_markdown(f"intro\n{code}\nafter\n")
    assert chunks == [Chunk(f"intro\n\n{code}\n\nafter", "")]
