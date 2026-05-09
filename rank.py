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

    def compare_responses(self, query: str, responses: list) -> list:
        '''
        Compare a list of response from the LLM and return a list of tuples containing the response and its rank
        '''
        possible_ranks = []
        for i in range(len(responses)):
            possible_ranks.append(i)
        ranks: List[tuple] = []
        for i in range(len(responses)):
            rank = possible_ranks.pop(
                random.randint(0, len(possible_ranks) - 1))
            ranks.append((responses[i], rank + 1))
            # return a list of tuples containing the response and a random rank for now
        return ranks
