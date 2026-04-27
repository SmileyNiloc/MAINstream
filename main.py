

from concurrent.futures import ThreadPoolExecutor
import queue

import customtkinter
import threading
from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


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
            text_color=("#111827", "#F9FAFB"),
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
        self.geometry("960x720")
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
        self.button = customtkinter.CTkButton(
            self,
            text="Query LLMs",
            command=self.button_callback,
            height=42,
            corner_radius=14,
        )
        self.button.grid(row=1, column=0, padx=24, pady=(0, 24), sticky="ew")

        self.check_queue_for_updates()

    def button_callback(self):
        # Start the query worker in a separate thread
        apis = self._llm_handler._apis
        self._create_empty_cards(len(apis))

        query_thread = threading.Thread(target=self.query_worker)
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

    def _create_empty_cards(self, num_cards):
        '''
        Create empty cards in the UI for the responses
        '''
        # Clear existing cards if any
        for widget in self.responses_frame.winfo_children():
            widget.destroy()
        self._textDisplays.clear()

        for i in range(num_cards):
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
                text=f"Response {i + 1}",
                font=("Segoe UI Semibold", 14),
                anchor="w",
            )
            title.grid(row=0, column=0, padx=16, pady=(14, 8), sticky="ew")

            # Make a new text display widget for each response and add it to the card
            self._textDisplays[i] = textDisplay(card, width=240, height=720)

            self._textDisplays[i].grid(
                row=1, column=0, padx=16, pady=(0, 16), sticky="nsew"
            )

    def query_worker(self, query="test"):
        '''
        Worker function to query the LLM APIs and update the UI with the responses
        '''

        apis = self._llm_handler._apis

        with ThreadPoolExecutor() as executor:
            for index, api in enumerate(apis):
                executor.submit(self._read_stream_to_queue, api, query, index)

    def _read_stream_to_queue(self, api, query, index):
        '''
        Read the response stream from the API and add it to the queue
        '''
        try:
            if hasattr(api, 'query_stream'):
                # Handle streaming APIs
                for chunk in api.query_stream(query):
                    self.response_queue.put({"index": index, "text": chunk})
            else:
                # Fallback for non-streaming APIs
                full_text = api.query(query)
                self.response_queue.put({"index": index, "text": full_text})

        except Exception as e:
            self.response_queue.put(
                {"index": index, "text": f"\n[Error: {e}]"})


class llmApi():
    '''
    Parent class for LLM APIs, with child classes for each specific API that implement the details of how to send queries and handle responses for that API
    '''

    def __init__(self):

        pass

    def query(self, query):
        '''
        Send a query to the LLM API and return the response
        '''

        pass

    def query_stream(self, query):
        '''
        Send a query to the LLM API and return a stream of responses (if the API supports streaming)
        '''
        # By default, just call the regular query method if streaming is not implemented
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

    def __init__(self, api_key):

        super().__init__()
        self._api_key = api_key
        self._client = genai.Client(api_key=self._api_key)

    def query(self, query):
        '''
        Send a query to the Gemini API and return the response
        '''
        response = self._client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=query
        )
        return response.text

    def query_stream(self, query):
        '''
        Send a query to the Gemini API and return the response
        '''
        response_stream = self._client.models.generate_content_stream(
            model="gemini-3-flash-preview",
            contents=query
        )

        for chunk in response_stream:
            if chunk.text:
                yield chunk.text


main_llm_handler = llmApiHandler()
if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY not found. Add it to .env as GEMINI_API_KEY=... or export it in your shell."
    )
main_llm_handler.add_api(geminiApi(GEMINI_API_KEY))

app = App(llm_handler=main_llm_handler)
app.mainloop()
