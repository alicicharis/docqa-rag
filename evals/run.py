"""Model-graded eval: answer every question in questions.json and score it with a judge.

Run `docqa ingest` first, then: uv run python evals/run.py
"""

import json
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import TypedDict

from anthropic import Anthropic

from docqa_rag import answer, embeddings, store
from docqa_rag.config import ANSWER_MODEL, TOP_K, require_env

JUDGE_MODEL = "claude-sonnet-5-5"
QUESTIONS = Path(__file__).with_name("questions.json")
RESULTS_DIR = Path(__file__).with_name("results")
UNANSWERABLE = (
    "The documents do not contain the answer. A correct solution says it doesn't know."
)

GRADE_SCHEMA = {
    "type": "object",
    "properties": {
        "strengths": {"type": "array", "items": {"type": "string"}},
        "weaknesses": {"type": "array", "items": {"type": "string"}},
        "reasoning": {"type": "string"},
        "score": {"type": "number"},
    },
    "required": ["strengths", "weaknesses", "reasoning", "score"],
    "additionalProperties": False,
}


class Case(TypedDict):
    question: str
    answer: str | None


class Grade(TypedDict):
    strengths: list[str]
    weaknesses: list[str]
    reasoning: str
    score: float


def grade_prompt(question: str, reference: str, output: str) -> str:
    return f"""You are an expert evaluator of question-answering systems. \
Your task is to evaluate an answer to a question about a company's documents \
against a reference answer. A good answer states the reference's facts and \
contradicts none of them. Wording, format and extra correct detail don't matter.

Original Task:
<task>
{question}
</task>

Reference Answer:
<reference>
{reference}
</reference>

Solution to Evaluate:
<solution>
{output}
</solution>

Output Format
Provide your evaluation as a structured JSON object with the following fields, \
in this specific order:
- "strengths": An array of 1-3 key strengths
- "weaknesses": An array of 1-3 key areas for improvement
- "reasoning": A concise explanation of your overall assessment
- "score": A number between 1-10

Respond with JSON. Keep your response concise and direct.
Example response shape:
{{
"strengths": string[],
"weaknesses": string[],
"reasoning": string,
"score": number
}}"""


def grade(client: Anthropic, question: str, reference: str, output: str) -> Grade:
    response = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=16000,
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": GRADE_SCHEMA},
        },
        messages=[
            {"role": "user", "content": grade_prompt(question, reference, output)}
        ],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"the judge declined to grade: {question}")
    text = next(b.text for b in response.content if b.type == "text")
    result: Grade = json.loads(text)
    return result


def main() -> None:
    require_env("OPENAI_API_KEY", "ANTHROPIC_API_KEY")
    cases: list[Case] = json.loads(QUESTIONS.read_text())
    collection = store.existing_collection()
    vectors = embeddings.embed([c["question"] for c in cases])
    client = Anthropic()
    graded: list[dict[str, object]] = []
    scores: list[float] = []
    for case, vector in zip(cases, vectors, strict=True):
        results = store.query(collection, vector, TOP_K)
        output = answer.generate(case["question"], results)
        reference = case["answer"] or UNANSWERABLE
        g = grade(client, case["question"], reference, output)
        scores.append(g["score"])
        graded.append({**case, "output": output, **g})
        print(f"[{g['score']:g}/10] {case['question']}")
        print(f"  answer: {output}")
        print(f"  reasoning: {g['reasoning']}")
    mean_score = mean(scores)
    print(f"\nMean score: {mean_score:.2f}/10 over {len(scores)} questions")

    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"{datetime.now():%Y%m%d-%H%M%S}.json"
    run = {
        "answer_model": ANSWER_MODEL,
        "judge_model": JUDGE_MODEL,
        "top_k": TOP_K,
        "mean_score": mean_score,
        "results": graded,
    }
    path.write_text(json.dumps(run, indent=2) + "\n")
    print(f"Saved {path}")


if __name__ == "__main__":
    main()
