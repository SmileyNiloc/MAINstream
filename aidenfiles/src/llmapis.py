from typing import Iterator, Union
import openai
from google import genai


class llmApi():
    '''
    Parent class for LLM APIs, with child classes for each specific API that implement the details of how to send queries and handle responses for that API
    '''

    def __init__(self, name):

        self._name = name

    def query(self, query) -> str | None:
        '''
        Send a query to the LLM API and return the response
        '''

        pass

    def query_stream(self, query) -> Union[str, None, Iterator[str]]:
        '''
        Send a query to the LLM API and return a stream of responses (if the API supports streaming).
        By default, call the regular query method which may return a full string (non-streaming).
        Child classes may override to return an iterator/generator yielding string chunks.
        '''
        return self.query(query)


class llmApiHandler():
    '''
    Handles communication with LLM APIs, with a child class for each API that implements the specific details of how to send queries and handle responses for that API
    '''

    def __init__(self):
        self._apis = []
        pass

    def add_api(self, api: llmApi):
        '''
        Add an LLM API to the handler
        '''
        self._apis.append(api)

    def query_all(self, query):
        '''
        Send a query to all LLM APIs and return the responses
        '''
        responses = []
        for api in self._apis:
            response = api.query(query)
            responses.append(response)
        return responses


class geminiApi(llmApi):
    '''
    A class for handling communication with the Gemini API
    '''

    def __init__(self, api_key, model="gemini-3.1-flash-lite", name=None):

        super().__init__(name if name else model)
        self._api_key = api_key
        self._client = genai.Client(api_key=self._api_key)
        self._model = model

    def query(self, query):
        '''
        Send a query to the Gemini API and return the response
        '''
        response = self._client.models.generate_content(
            model=self._model,
            contents=query
        )
        return response.text

    def query_stream(self, query):
        '''
        Send a query to the Gemini API and return the response
        '''
        response_stream = self._client.models.generate_content_stream(
            model=self._model,
            contents=query
        )

        for chunk in response_stream:
            if chunk.text:
                yield chunk.text


class openaiApi(llmApi):
    '''
    A class for handling communication with the OpenAI API
    '''

    def __init__(self, api_key, name=None):

        super().__init__(name if name else "OpenAI API")
        self._api_key = api_key
        self._client = openai.OpenAI(api_key=self._api_key)

    def query(self, query):
        '''
        Send a query to the OpenAI API and return the response
        '''
        response = self._client.responses.create(
            model="o3-mini",
            input=[
                {"role": "user", "content": query}
            ]
        )
        return response.output_text

    def query_stream(self, query: str) -> str | None:
        """
        Send a query to the OpenAI Responses API and return the full response text.
        """
        try:
            stream = self._client.responses.create(
                model="o3-mini",
                input=[
                    {"role": "user", "content": query}
                ],
                stream=True,
            )

            chunks = []
            for event in stream:
                if event.type == "response.output_text.delta":
                    content = getattr(event, 'text', None)

                    if not content and hasattr(event, 'delta'):
                        content = getattr(event.delta, 'text', None)

                    if content:
                        chunks.append(content)

            return ''.join(chunks)

        except Exception as e:
            print(f"Streaming error: {e}")
            return f"\n[Error communicating with API: {e}]"


class openRouterApi(llmApi):
    '''
    A class for handling communication with the OpenRouter API
    '''

    def __init__(self, api_key, name=None, model="inclusionai/ring-2.6-1t:free", url="https://openrouter.ai/api/v1"):

        super().__init__(name if name else model)
        self._api_key = api_key
        self._client = openai.OpenAI(
            base_url=url, api_key=self._api_key)
        self._model = model
        self._extra_headers = {
            "X-Title": "mAInstream",      # Optional: Your app name for rankings
        }

    def query(self, query):
        '''
        Send a query to the OpenRouter API and return the response
        '''

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "user", "content": query}
            ],
            extra_headers=self._extra_headers
        )
        return response.choices[0].message.content

