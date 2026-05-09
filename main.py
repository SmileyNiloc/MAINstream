

import queue
from typing import Union, Iterator


import customtkinter
import threading
from google import genai
import os
from dotenv import load_dotenv

import openai

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPEN_ROUTER_API_KEY = os.getenv("OPEN_ROUTER_API_KEY")


class textDisplay(customtkinter.CTkTextbox):
    '''
    A custom text display widget that is read-only and can be used to display text in the app
    '''

    def __init__(self, master=None, ** kwargs):
        super().__init__(
            master,
            corner_radius=14,
            border_width=1,
            border_color=("#D1D5DB", "#374151"),
            fg_color=("#FFFFFF", "#1F2937"),
            text_color="#111827",
            scrollbar_button_color=("#9CA3AF", "#6B7280"),
            scrollbar_button_hover_color=("#6B7280", "#9CA3AF"),
            font=("Segoe UI", 13),
            wrap="word",
            **kwargs,
        )
        # Make it read-only
        self.configure(state="disabled")

    def add_text(self, text):
        '''
        Add text to the text display widget
        '''
        # Have to temporarily make it editable to add text, then make it read-only again
        self.configure(state="normal")
        self.delete("1.0", "end")
        if isinstance(text, list):
            for item in text:
                self.insert("end", item + "\n")
        elif isinstance(text, str):
            self.insert("end", text + "\n")
        self.configure(state="disabled")

    def append_text(self, text):
        '''
        Append text to the text display widget without clearing it
        '''
        self.configure(state="normal")
        self.insert("end", text)
        self.yview("end")
        self.configure(state="disabled")


class App(customtkinter.CTk):
    def __init__(self, llm_handler=None):
        super().__init__()

        self._llm_handler = llm_handler

        self.title("MAINstream")
        self.geometry("1180x960")
        self.minsize(860, 620)
        # Set the window to use a grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.response_queue = queue.Queue()
        self.current_card_index = 0
        self._responses = []
        self._textDisplays = {}
        self.responses_frame = customtkinter.CTkScrollableFrame(
            self,
            label_text="Model responses",
            corner_radius=18,
            border_width=1,
            border_color=("#D1D5DB", "#374151"),
            fg_color=("#F8FAFC", "#111827"),
            orientation="horizontal"
        )
        self.responses_frame.grid(
            row=0, column=0, padx=24, pady=(24, 12), sticky="nsew"
        )
        self.queryInput = customtkinter.CTkEntry(
            self,
            placeholder_text="Enter your query here...",
            height=42,
            corner_radius=14,
        )
        self.queryInput.grid(
            row=1, column=0, padx=24, pady=(0, 12), sticky="ew"
        )
        self.button = customtkinter.CTkButton(
            self,
            text="Query LLMs",
            command=self.button_callback,
            height=42,
            corner_radius=14,
        )
        self.button.grid(row=2, column=0, padx=24, pady=(0, 24), sticky="ew")

        self.check_queue_for_updates()

    def button_callback(self):
        query = self.queryInput.get()
        if not query:
            return

        if self._llm_handler is None:
            print("No LLM handler provided.")
            return
        # Start the query worker in a separate thread
        apis = self._llm_handler._apis
        self._create_empty_cards(apis)

        query_thread = threading.Thread(
            target=self.query_worker, args=(query,))
        query_thread.start()

    def check_queue_for_updates(self):
        """Runs on the MAIN thread."""
        try:
            # Process everything currently in the queue to keep the UI snappy
            while True:
                data = self.response_queue.get_nowait()

                card_index = data["index"]
                chunk = data["text"]

                # Append the text to the specific widget
                # (You will need to ensure your textDisplay class has an append method)
                self._textDisplays[card_index].append_text(chunk)

        except queue.Empty:
            pass
        finally:
            # Check again in 50ms for a smoother streaming visual
            self.after(50, self.check_queue_for_updates)

    def _create_empty_cards(self, apis):
        '''
        Create empty cards in the UI for the responses
        '''
        # Clear existing cards if any
        for widget in self.responses_frame.winfo_children():
            widget.destroy()
        self._textDisplays.clear()

        for i, api in enumerate(apis):
            api_name = getattr(api, "_name", None) or f"Response {i + 1}"
            card = customtkinter.CTkFrame(
                self.responses_frame,
                corner_radius=18,
                border_width=1,
                border_color=("#E5E7EB", "#374151"),
                fg_color=("#FFFFFF", "#111827"),
            )
            card.grid(row=0, column=i, padx=8, pady=8, sticky="nsew")
            card.grid_columnconfigure(0, weight=1)

            title = customtkinter.CTkLabel(
                card,
                text=api_name,
                font=("Segoe UI Semibold", 14),
                anchor="w",
            )
            title.grid(row=0, column=0, padx=16, pady=(14, 8), sticky="ew")

            # Make a new text display widget for each response and add it to the card
            self._textDisplays[i] = textDisplay(card, width=340, height=540)

            self._textDisplays[i].grid(
                row=1, column=0, padx=16, pady=(0, 16), sticky="nsew"
            )

    def query_worker(self, query):
        '''
        Worker function to query the LLM APIs and update the UI with the responses
        '''
        if self._llm_handler is None:
            return
        apis = self._llm_handler._apis

        for index, api in enumerate(apis):
            worker = threading.Thread(
                target=self._api_worker,
                args=(api, query, index),
                daemon=True,
            )
            worker.start()

    def _api_worker(self, api, query, index):
        '''
        Read the response stream from one API and add it to the queue
        '''
        try:
            response = api.query_stream(query)

            if isinstance(response, str) or response is None:
                if response:
                    self.response_queue.put({"index": index, "text": response})
                return

            for chunk in response:
                self.response_queue.put({"index": index, "text": chunk})

        except Exception as e:
            self.response_queue.put(
                {"index": index, "text": f"\n[Error: {e}]"})


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
                {"role": "user", "content": "Hello! What can you do?"}
            ],
            extra_headers=self._extra_headers
        )
        return response.choices[0].message.content


main_llm_handler = llmApiHandler()
if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY not found. Add it to .env as GEMINI_API_KEY=... or export it in your shell."
    )
main_llm_handler.add_api(geminiApi(GEMINI_API_KEY, name="Gemini API"))
main_llm_handler.add_api(openRouterApi(
    OPEN_ROUTER_API_KEY, name="OpenRouter API"))
# if OPENAI_API_KEY:
# main_llm_handler.add_api(openaiApi(OPENAI_API_KEY))
app = App(llm_handler=main_llm_handler)
app.mainloop()
