import tiktoken

from docqa_rag.config import EMBED_MAX_INPUTS, EMBED_MAX_TOKENS, TOKENIZER
from docqa_rag.embeddings import batch_texts


def test_batch_texts_splits_at_max_inputs() -> None:
    texts = ["a"] * (EMBED_MAX_INPUTS + 1)
    batches = batch_texts(texts)
    assert [len(b) for b in batches] == [EMBED_MAX_INPUTS, 1]


def test_batch_texts_splits_before_max_tokens() -> None:
    encoding = tiktoken.get_encoding(TOKENIZER)
    text = "hello " * 9_999
    tokens = len(encoding.encode(text))
    per_batch = EMBED_MAX_TOKENS // tokens
    texts = [text] * (per_batch + 1)
    batches = batch_texts(texts)
    assert [len(b) for b in batches] == [per_batch, 1]
