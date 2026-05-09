import random
from typing import List


class Ranker:
    '''
    A class for ranking responses from an LLM
    '''

    def __init__(self):
        # SETUP AND AI INSTANCE
        # self._client = genai.Client(api_key=GEMINI_API_KEY)
        pass

    def rank_response(self, query: str, response: str) -> int:
        '''
        Rank a response from the LLM on a scale of 1 to 10
        '''
        # return a random integer between 1 and 10 for now
        return random.randint(1, 10)

    def compare_responses(self, query: str, responses: list[tuple]) -> List[tuple]:
        '''
        Compare responses and return comparative ranks aligned by index.
        A lower rank value means a better relative result (1 = best).
        '''
        if not responses:
            return []

        ids = [rid for rid, _ in responses]
        possible_ranks = list(range(1, len(ids) + 1))
        random.shuffle(possible_ranks)
        # Assign ranks to ids in positional order (placeholder random ordering)
        return [(possible_ranks[i], ids[i]) for i in range(len(ids))]
