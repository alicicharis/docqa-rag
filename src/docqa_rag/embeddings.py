from collections.abc import Callable

import tiktoken
from openai import OpenAI

from docqa_rag.config import (
    EMBED_MAX_INPUTS,
    EMBED_MAX_TOKENS,
    EMBEDDING_MODEL,
    TOKENIZER,
)

Embedder = Callable[[list[str]], list[list[float]]]


def batch_texts(texts: list[str]) -> list[list[str]]:
    """Group texts in order without exceeding the per-request input or token limits."""
    encoding = tiktoken.get_encoding(TOKENIZER)
    batches: list[list[str]] = []
    current: list[str] = []
    current_tokens = 0
    for text in texts:
        tokens = len(encoding.encode(text, disallowed_special=()))
        if current and (
            len(current) >= EMBED_MAX_INPUTS
            or current_tokens + tokens > EMBED_MAX_TOKENS
        ):
            batches.append(current)
            current = []
            current_tokens = 0
        current.append(text)
        current_tokens += tokens
    if current:
        batches.append(current)
    return batches


def embed(texts: list[str]) -> list[list[float]]:
    client = OpenAI()
    vectors: list[list[float]] = []
    for batch in batch_texts(texts):
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        vectors.extend(
            item.embedding for item in sorted(response.data, key=lambda d: d.index)
        )
    return vectors
