import os

from anthropic import Anthropic

from docqa_rag.config import ANSWER_MAX_TOKENS, ANSWER_MODEL
from docqa_rag.store import SearchResult

DONT_KNOW = "I don't know based on the indexed documents."

SYSTEM_PROMPT = (
    "Answer the user's question using only the documents provided in the user "
    "message. Answer directly and concisely in plain text. Do not cite or "
    "mention sources or file names. If the documents "
    f"do not contain the answer, reply with exactly: {DONT_KNOW}"
)


def build_prompt(question: str, results: list[SearchResult]) -> str:
    documents: list[str] = []
    for r in results:
        attrs = f'source="{os.path.relpath(r.source)}"'
        if r.heading_path:
            attrs += f' section="{r.heading_path}"'
        documents.append(f"<document {attrs}>\n{r.text}\n</document>")
    body = "\n".join(documents)
    return f"<documents>\n{body}\n</documents>\n\nQuestion: {question}"


def generate(question: str, results: list[SearchResult]) -> str:
    response = Anthropic().messages.create(
        model=ANSWER_MODEL,
        max_tokens=ANSWER_MAX_TOKENS,
        thinking={"type": "between_tools"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_prompt(question, results)}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("the model declined to answer")
    return "".join(b.text for b in response.content if b.type == "text").strip()
