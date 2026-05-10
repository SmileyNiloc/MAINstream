from typing import Iterator, Union
import openai
import time
import threading
from google import genai


class llmApi():
    '''
    Parent class for LLM APIs, with child classes for each specific API that implement
    the details of how to send queries and handle responses for that API.
    '''

    def __init__(self, name):
        self._name = name

    def query(self, query, system_prompt=None) -> str | None:
        '''
        Send a query to the LLM API and return the response.
        '''
        pass

    def query_stream(self, query, system_prompt=None) -> Union[str, None, Iterator[str]]:
        '''
        Send a query to the LLM API and return a stream of responses (if supported).
        Child classes may override to return an iterator/generator yielding string chunks.
        '''
        return self.query(query, system_prompt=system_prompt)


class llmApiHandler():
    def __init__(self):
        self._apis = []
        self._rate_limit_lock = threading.Lock()
        self._last_request_time = 0
        self._min_delay = 5.0  # Seconds to wait between ANY two requests

    def add_api(self, api: llmApi):
        self._apis.append(api)

    def safe_query(self, api, query, system_prompt):
        """Wraps the API call in a lock to enforce a delay."""
        with self._rate_limit_lock:
            elapsed = time.time() - self._last_request_time
            if elapsed < self._min_delay:
                time.sleep(self._min_delay - elapsed)
            
            self._last_request_time = time.time()
            return api.query_stream(query, system_prompt=system_prompt)


class geminiApi(llmApi):
    '''
    A class for handling communication with the Gemini API.
    '''

    def __init__(self, api_key, model="gemini-2.0-flash-lite", name=None):
        super().__init__(name if name else model)
        self._api_key = api_key
        self._client = genai.Client(api_key=self._api_key)
        self._model = model

    def _build_contents(self, query, system_prompt=None):
        '''Build a contents list, prepending a system turn if a prompt is given.'''
        if system_prompt:
            return [
                {"role": "user", "parts": [{"text": system_prompt}]},
                {"role": "model", "parts": [{"text": "Understood. I will follow those instructions."}]},
                {"role": "user", "parts": [{"text": query}]},
            ]
        return query

    def query(self, query, system_prompt=None):
        response = self._client.models.generate_content(
            model=self._model,
            contents=self._build_contents(query, system_prompt),
        )
        return response.text

    def query_stream(self, query, system_prompt=None):
        response_stream = self._client.models.generate_content_stream(
            model=self._model,
            contents=self._build_contents(query, system_prompt),
        )
        for chunk in response_stream:
            if chunk.text:
                yield chunk.text


class openaiApi(llmApi):
    '''
    A class for handling communication with the OpenAI API.
    '''

    def __init__(self, api_key, name=None):
        super().__init__(name if name else "OpenAI API")
        self._api_key = api_key
        self._client = openai.OpenAI(api_key=self._api_key)

    def _build_input(self, query, system_prompt=None):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": query})
        return messages

    def query(self, query, system_prompt=None):
        response = self._client.responses.create(
            model="o3-mini",
            input=self._build_input(query, system_prompt),
        )
        return response.output_text

    def query_stream(self, query: str, system_prompt=None) -> str | None:
        try:
            stream = self._client.responses.create(
                model="o3-mini",
                input=self._build_input(query, system_prompt),
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
    A class for handling communication with the OpenRouter API.
    '''

    def __init__(self, api_key, name=None, model="inclusionai/ring-2.6-1t:free",
                 url="https://openrouter.ai/api/v1"):
        super().__init__(name if name else model)
        self._api_key = api_key
        self._client = openai.OpenAI(base_url=url, api_key=self._api_key)
        self._model = model
        self._extra_headers = {
            "X-Title": "mAInstream",
        }

    def _build_messages(self, query, system_prompt=None):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": query})
        return messages

    def query(self, query, system_prompt=None):
        response = self._client.chat.completions.create(
            model=self._model,
            messages=self._build_messages(query, system_prompt),
            extra_headers=self._extra_headers,
        )
        return response.choices[0].message.content

    def query_stream(self, query, system_prompt=None):
        '''
        Stream the response from OpenRouter chunk by chunk.
        Yields string chunks as they arrive.
        '''
        try:
            stream = self._client.chat.completions.create(
                model=self._model,
                messages=self._build_messages(query, system_prompt),
                extra_headers=self._extra_headers,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content
        except Exception as e:
            print(f"[openRouterApi] Streaming error: {e}")
            yield f"\n[Error communicating with API: {e}]"