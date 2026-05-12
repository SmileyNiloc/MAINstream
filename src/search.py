# src/search.py (or wherever you placed the search utility)
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS
from src.llmapis import llmApi  # Assuming you can pass your handler here


def get_synthesized_search_context(query: str, fast_api: llmApi) -> str:
    """Fetches search results and uses a fast LLM to synthesize them."""
    try:
        # 1. Get raw results
        results = DDGS().text(query, max_results=3)
        raw_context = ""
        for i, res in enumerate(results):
            raw_context += f"Result {i+1}: {res['body']}\n"

        if not raw_context:
            return "No search results found."

        # 2. Synthesize the results
        synthesis_prompt = f"""
        You are a factual research assistant. Synthesize the following search results into a concise, 
        factual summary to answer the query: "{query}". 
        Rely ONLY on the provided search results. If the results do not contain the answer, state that.
        
        Search Results:
        {raw_context}
        """

        # Use a fast API (e.g., the first one in your handler, or a dedicated instance)
        synthesis = fast_api.query(synthesis_prompt)
        if not synthesis:
            raise ValueError("Empty synthesis from LLM API")
        return synthesis.strip()

    except Exception as e:
        print(f"[Search] Failed to fetch/synthesize results: {e}")
        return f"Search context unavailable. Error: {e}"
