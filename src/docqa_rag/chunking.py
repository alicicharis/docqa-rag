import re
from dataclasses import dataclass
from functools import cache

import tiktoken

from docqa_rag.config import CHUNK_OVERLAP, CHUNK_TOKENS, TOKENIZER

_HEADING = re.compile(r"^(#{1,6}) +(.*?)\s*$")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")


@dataclass(frozen=True)
class Chunk:
    text: str
    heading_path: str


@cache
def _encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding(TOKENIZER)


def _strip_front_matter(lines: list[str]) -> list[str]:
    if not lines or lines[0] != "---":
        return lines
    for i in range(1, len(lines)):
        if lines[i] in ("---", "..."):
            return lines[i + 1 :]
    return lines


def _sections(lines: list[str]) -> list[tuple[str, list[str]]]:
    """Split into (heading_path, paragraphs) sections, in document order."""
    sections: list[tuple[str, list[str]]] = []
    stack: list[tuple[int, str]] = []
    paragraphs: list[str] = []
    current: list[str] = []
    fence: str | None = None

    def flush_paragraph() -> None:
        if current:
            paragraphs.append("\n".join(current))
            current.clear()

    def flush_section() -> None:
        flush_paragraph()
        if paragraphs:
            path = " > ".join(title for _, title in stack)
            sections.append((path, paragraphs.copy()))
        paragraphs.clear()

    for line in lines:
        fence_match = _FENCE.match(line)
        if fence is not None:
            current.append(line)
            if (
                fence_match
                and line.strip() == fence_match.group(1)
                and fence_match.group(1).startswith(fence)
            ):
                fence = None
                flush_paragraph()
            continue
        if fence_match:
            flush_paragraph()
            fence = fence_match.group(1)[:1] * len(fence_match.group(1))
            current.append(line)
            continue
        heading = _HEADING.match(line)
        if heading:
            flush_section()
            level = len(heading.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, heading.group(2)))
        elif line.strip() == "":
            flush_paragraph()
        else:
            current.append(line)
    flush_section()
    return sections


def _pack(path: str, paragraphs: list[str]) -> list[Chunk]:
    enc = _encoding()
    chunks: list[Chunk] = []
    pack: list[str] = []

    def flush() -> None:
        if pack:
            chunks.append(Chunk("\n\n".join(pack), path))
            pack.clear()

    for paragraph in paragraphs:
        tokens = enc.encode(paragraph)
        if len(tokens) > CHUNK_TOKENS:
            flush()
            stride = CHUNK_TOKENS - CHUNK_OVERLAP
            for start in range(0, len(tokens), stride):
                window = tokens[start : start + CHUNK_TOKENS]
                chunks.append(Chunk(enc.decode(window), path))
                if start + CHUNK_TOKENS >= len(tokens):
                    break
        elif pack and len(enc.encode("\n\n".join([*pack, paragraph]))) > CHUNK_TOKENS:
            flush()
            pack.append(paragraph)
        else:
            pack.append(paragraph)
    flush()
    return chunks


def chunk_markdown(markdown: str) -> list[Chunk]:
    lines = _strip_front_matter(markdown.splitlines())
    return [
        chunk
        for path, paragraphs in _sections(lines)
        for chunk in _pack(path, paragraphs)
    ]
