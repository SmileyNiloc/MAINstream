import json
import os
import re
import time
from typing import List
from src.llmapis import llmApi


_SCORE_PROMPT = """\
You are an expert AI response evaluator. Score the following LLM response to the given query.
IMPORTANT: ALWAYS RESPOND IN ENGLISH.

Query:
{query}

Response:
{response}

Rate the response on a scale of 1 to 10 based on:
- Accuracy and correctness
- Clarity and readability
- Completeness
- Conciseness (penalise unnecessary padding)

Reply with ONLY a JSON object in this exact format, no other text:
{{"score": <integer 1-10>, "reason": "<one short sentence>"}}
"""

_COMPARE_PROMPT = """\
You are an expert AI response evaluator. Rank the following responses to the query from best to worst.
Each response includes a prior independent score (1-10) from an evaluator. Treat that score as a strong
signal: your comparative rank should generally agree with the scores (a higher-scored response should
rank above a lower-scored one) unless side-by-side comparison reveals a clear reason to deviate, in
which case briefly justify the deviation to yourself before answering.
If a response is an error, exclude it from the pool. So if there are 8 errors, the total possible ranks is first and second.
Dont assign a rank until all prompts are evaluated. Rank 1 is best, rank {n} is worst, where n is the number of non-error responses.
IMPORTANT: ALWAYS RESPOND IN ENGLISH.

Query:
{query}

Responses:
{responses}

Assign each response a unique comparative rank (1 = best, {n} = worst).
Consider accuracy, clarity, completeness, conciseness, AND the prior score shown for each response.

Reply with ONLY a JSON array in this exact format, no other text:
[{{"id": <response_id>, "rank": <integer>}}, ...]
Include every response id exactly once.
"""


class Ranker:
    """
    Ranks LLM responses using OpenRouter's owl-alpha judge.
    Falls back to a neutral score of 5 if the API call fails.
    """

    def __init__(self, llmapi: llmApi):
        self._llmapi = llmapi

    def _parse_json(self, text: str):
        """Strip markdown fences and parse JSON."""
        clean = re.sub(r"^```[a-z]*\n?|```$", "",
                       text.strip(), flags=re.MULTILINE).strip()
        return json.loads(clean)

    def rank_response(self, query: str, response: str) -> int:
        """
        Score a single response on a scale of 1–10.
        Returns 5 on any failure.
        """
        if not self._llmapi:
            return 5
        try:
            prompt = _SCORE_PROMPT.format(query=query, response=response)
            raw = self._llmapi.query(prompt)
            if not raw:
                raise ValueError("Empty response from ranker API")
            data = self._parse_json(raw)
            score = int(data["score"])
            time.sleep(30)
            return max(1, min(10, score))
        except Exception as e:
            print(f"[Ranker] rank_response failed: {e}")
            return 5

    def compare_responses(self, query: str, responses: list[tuple]) -> List[tuple]:
        """
        Compare responses and return a list of (rank, id) tuples.
        `responses` is a list of (id, text, score) tuples. The per-response score
        produced by rank_response is fed to the judge so the comparative rank
        stays consistent with the individual scores. A lower rank value means a
        better result (1 = best).
        Falls back to a score-descending ranking if the judge call fails or
        is unavailable.
        """
        if not responses:
            return []

        def _score_fallback():
            """Rank by prior score, highest first; missing scores treated as 0.
            Ties are broken by id so the output is deterministic."""
            ordered = sorted(
                responses,
                key=lambda r: (
                    -((r[2] if len(r) > 2 and r[2] is not None else 0)),
                    r[0] if len(r) > 0 and r[0] is not None else 0,
                ),
            )
            return [(i + 1, item[0]) for i, item in enumerate(ordered)]

        if not self._llmapi:
            return _score_fallback()

        try:
            # Only non-empty responses are shown to the judge, so `n` must match
            # the number we actually format into the prompt.
            shown = [
                (rid, text, score) for rid, text, score in responses if text
            ]
            formatted = "\n\n".join(
                f"[Response {rid}] (prior score: "
                f"{score if score is not None else 'n/a'}/10)\n{text}"
                for rid, text, score in shown
            )
            n = len(shown)
            prompt = _COMPARE_PROMPT.format(
                query=query, responses=formatted, n=n)
            raw = self._llmapi.query(prompt)
            if not raw:
                raise ValueError("Empty response from ranker API")
            data = self._parse_json(raw)
            # data is a list of {"id": ..., "rank": ...}
            return [(item["rank"], item["id"]) for item in data]
        except Exception as e:
            print(f"[Ranker] compare_responses failed: {e}")
            return _score_fallback()
