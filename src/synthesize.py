
import json
import logging
from typing import List
from src.llmapis import llmApi


logger = logging.getLogger(__name__)


_SYNTHESIZE_PROMPT = """\
You are an expert AI response synthesizer. Synthesize the following responses into a single coherent response.
IMPORTANT: ALWAYS RESPOND IN ENGLISH.

Query:
{query}

Responses:
{responses}

Synthesize a single coherent response that:
- Incorporates the most important and accurate information from all responses
- Eliminates redundancy and contradictions
- Maintains clarity and readability
- Is concise and focused on answering the original query
- Creates a unified narrative that flows naturally

Reply with ONLY the synthesized response text, no other formatting or explanation.
"""


class Synthesizer:
    """
    Synthesizes multiple LLM responses into a single coherent response.
    Uses an LLM API to create unified responses.
    Falls back to a concatenated summary if the API call fails.
    """

    def __init__(self, llmapi: llmApi = None):
        self._llmapi = llmapi
        logger.debug("Synthesizer initialized with llmapi=%s",
                     type(llmapi).__name__ if llmapi else "None")

    def _create_fallback_synthesize(self, responses: List[str]) -> str:
        """Create a simple concatenated summary as fallback."""
        if not responses:
            return ""
        summary = "Synthesis of responses:\n\n"
        for i, response in enumerate(responses, 1):
            summary += f"--- Response {i} ---\n{response}\n\n"
        return summary.strip()

    def synthesize_responses(self, query: str, responses: List[str]) -> str:
        """
        Synthesize multiple responses into a single coherent response.

        Args:
            query (str): The original query for context
            responses (List[str]): List of responses to synthesize

        Returns:
            str: The synthesized response. Returns fallback summary on failure.
        """
        if not responses:
            logger.debug("synthesize_responses: no responses provided")
            return ""

        if not self._llmapi:
            logger.debug(
                "synthesize_responses using fallback because no LLM API is configured")
            result = self._create_fallback_synthesize(responses)
            print(f"[Synthesizer - Fallback]\n{result}\n")
            return result

        try:
            logger.debug(
                "Synthesizing responses: query_chars=%d response_count=%d",
                len(query),
                len(responses),
            )
            # Format responses for the prompt
            formatted_responses = "\n\n".join(
                f"[Response {i}]\n{response}"
                for i, response in enumerate(responses, 1)
            )

            prompt = _SYNTHESIZE_PROMPT.format(
                query=query,
                responses=formatted_responses
            )

            raw = self._llmapi.query(prompt)
            if not raw:
                raise ValueError("Empty response from synthesizer API")

            logger.debug("Received synthesizer API response")
            synthesized = raw.strip()

            # Print to terminal for testing
            print(
                f"[Synthesizer Output]\nQuery: {query}\n\nSynthesized Response:\n{synthesized}\n")

            return synthesized

        except Exception as e:
            logger.exception("synthesize_responses failed: %s", str(e))
            result = self._create_fallback_synthesize(responses)
            print(f"[Synthesizer - Error Fallback] {str(e)}\n{result}\n")
            return result
