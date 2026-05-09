import random


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
