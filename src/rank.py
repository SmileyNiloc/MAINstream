import json
import logging
import os
import re
import time
from typing import List
from src.llmapis import llmApi


logger = logging.getLogger(__name__)


_SCORE_PROMPT = """\
You are an expert AI response evaluator. Score the following LLM response to the given query.
IMPORTANT: ALWAYS RESPOND IN ENGLISH.

Query:
{query}

Response:
{response}

Rate the response on a scale of 0 to 10 based on:
- Accuracy and correctness
- Clarity and readability
- Completeness
- Conciseness (penalise unnecessary padding)

Where 0 is an unhelpful or harmful response
Where 1 is a barely helpful response
Where 10 is a perfect response that fully answers the query with no issues and goes above and beyond in helpfulness.

Reply with ONLY a JSON object in this exact format, no other text:
{{"score": <integer 0-10>, "reason": "<one short sentence>"}}
"""

_COMPARE_PROMPT = """\
You are an expert AI response evaluator. Rank the following responses to the query from best to worst.
Each response includes a prior independent score (0-10) from an evaluator. Treat that score as a strong
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
        logger.debug("Ranker initialized with llmapi=%s",
                     type(llmapi).__name__ if llmapi else "None")

    def _parse_json(self, text: str):
        """Strip markdown fences and parse JSON."""
        clean = re.sub(r"^```[a-z]*\n?|```$", "",
                       text.strip(), flags=re.MULTILINE).strip()
        if not clean:
            raise ValueError("Ranker API returned an empty JSON payload")

        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            start_candidates = [
                index for index in (clean.find("{"), clean.find("[")) if index != -1
            ]
            end_candidates = [clean.rfind("}"), clean.rfind("]")]
            if start_candidates and max(end_candidates) > min(start_candidates):
                return json.loads(clean[min(start_candidates):max(end_candidates) + 1])
            raise

    def rank_response(self, query: str, response: str) -> int:
        """
        Score a single response on a scale of 1–10.
        Returns 5 on any failure.
        """
        if not self._llmapi:
            logger.debug(
                "rank_response using fallback score because no LLM API is configured")
            return 5
        try:
            logger.debug(
                "Ranking single response: query_chars=%d response_chars=%d",
                len(query),
                len(response),
            )
            prompt = _SCORE_PROMPT.format(query=query, response=response)
            raw = self._llmapi.query(prompt)
            if not raw:
                raise ValueError("Empty response from ranker API")
            logger.debug("Received ranker API response for single score")
            data = self._parse_json(raw)
            score = int(data["score"])
            time.sleep(30)
            return max(1, min(10, score))
        except Exception:
            logger.exception("rank_response failed")
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

        def _normalize_response(response_item: tuple):
            response_id = response_item[0] if len(response_item) > 0 else None
            text = response_item[1] if len(
                response_item) > 1 and response_item[1] is not None else ""
            score = response_item[2] if len(response_item) > 2 else None
            return response_id, text, score

        normalized_responses = [
            _normalize_response(item) for item in responses]

        def _score_fallback():
            """Rank by prior score, highest first; missing scores treated as 0.
            Ties are broken by id so the output is deterministic."""
            ordered = sorted(
                normalized_responses,
                key=lambda r: (
                    -((r[2] if len(r) > 2 and r[2] is not None else 0)),
                    r[0] if len(r) > 0 and r[0] is not None else 0,
                ),
            )
            return [(i + 1, item[0]) for i, item in enumerate(ordered)]

        if not self._llmapi:
            logger.debug(
                "compare_responses using score fallback because no LLM API is configured")
            return _score_fallback()

        try:
            # Only non-empty responses are shown to the judge, so `n` must match
            # the number we actually format into the prompt.
            shown = [
                (rid, text, score) for rid, text, score in normalized_responses if text
            ]
            logger.debug(
                "Comparing responses: total=%d shown=%d",
                len(normalized_responses),
                len(shown),
            )
            formatted = "\n\n".join(
                f"[Response {rid}] (prior score: "
                f"{score if score is not None else 'n/a'}/10)\n{text}"
                for rid, text, score in shown
            )
            n = len(shown)
            prompt = _COMPARE_PROMPT.format(
                query=query, responses=formatted, n=n)
            raw = self._llmapi.query(prompt)
            logger.debug("Raw comparative ranking output from API: %r", raw)
            if not raw:
                raise ValueError("Empty response from ranker API")
            logger.debug(
                "Received ranker API response for comparative ranking")
            data = self._parse_json(raw)
            # data is a list of {"id": ..., "rank": ...}
            return [(int(item["rank"]), int(item["id"])) for item in data]
        except Exception:
            logger.exception("compare_responses failed")
            return _score_fallback()
