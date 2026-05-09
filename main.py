
import sqlite3
import queue
from typing import Union, Iterator
from datetime import datetime
from uuid import uuid4


import customtkinter
import threading
from google import genai
import os
from dotenv import load_dotenv

import openai
from rank import Ranker

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPEN_ROUTER_API_KEY = os.getenv("OPEN_ROUTER_API_KEY")

DB_NAME = "mainstream.db"


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
    def __init__(self, llm_handler=None, database_manager=None):
        super().__init__()

        self._llm_handler = llm_handler
        self._database_manager = database_manager
        self._loaded_history_query = None
        self._ranker = Ranker()
        self._latest_query_results = {}
        self._results_lock = threading.Lock()

        self.title('MAINstream')
        self.geometry('1180x960')
        self.minsize(860, 620)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.response_queue = queue.Queue()
        self.current_card_index = 0
        self._responses = []
        self._textDisplays = {}
        self._history_buttons = []

        self.sidebar_frame = customtkinter.CTkFrame(
            self,
            corner_radius=18,
            border_width=1,
            border_color=('#D1D5DB', '#374151'),
            fg_color=('#F8FAFC', '#111827'),
            width=290,
        )
        self.sidebar_frame.grid(
            row=0, column=0, padx=(24, 12), pady=24, sticky='nsew'
        )
        self.sidebar_frame.grid_columnconfigure(0, weight=1)
        self.sidebar_frame.grid_rowconfigure(3, weight=1)

        sidebar_title = customtkinter.CTkLabel(
            self.sidebar_frame,
            text='Query history',
            font=('Segoe UI Semibold', 18),
            anchor='w',
        )
        sidebar_title.grid(row=0, column=0, padx=18,
                           pady=(18, 10), sticky='ew')

        self.new_query_button = customtkinter.CTkButton(
            self.sidebar_frame,
            text='New Query',
            command=self.show_new_query_mode,
            height=40,
            corner_radius=14,
        )
        self.new_query_button.grid(
            row=1, column=0, padx=18, pady=(0, 12), sticky='ew'
        )

        history_label = customtkinter.CTkLabel(
            self.sidebar_frame,
            text='Saved queries',
            font=('Segoe UI Semibold', 14),
            anchor='w',
        )
        history_label.grid(row=2, column=0, padx=18, pady=(0, 8), sticky='new')

        self.history_frame = customtkinter.CTkScrollableFrame(
            self.sidebar_frame,
            corner_radius=14,
            border_width=1,
            border_color=('#E5E7EB', '#374151'),
            fg_color=('#FFFFFF', '#1F2937'),
            orientation='vertical',
        )
        self.history_frame.grid(
            row=3, column=0, padx=18, pady=(0, 18), sticky='nsew'
        )

        self.main_frame = customtkinter.CTkFrame(
            self,
            corner_radius=18,
            border_width=1,
            border_color=('#D1D5DB', '#374151'),
            fg_color=('#F8FAFC', '#111827'),
        )
        self.main_frame.grid(
            row=0, column=1, padx=(12, 24), pady=24, sticky='nsew'
        )
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

        self.responses_frame = customtkinter.CTkScrollableFrame(
            self.main_frame,
            label_text='Model responses',
            corner_radius=18,
            border_width=1,
            border_color=('#D1D5DB', '#374151'),
            fg_color=('#F8FAFC', '#111827'),
            orientation='horizontal',
        )
        self.responses_frame.grid(
            row=0, column=0, padx=18, pady=(18, 12), sticky='nsew'
        )

        self.queryInput = customtkinter.CTkEntry(
            self.main_frame,
            placeholder_text='Enter your query here...',
            height=42,
            corner_radius=14,
        )
        self.queryInput.grid(
            row=1, column=0, padx=18, pady=(0, 12), sticky='ew'
        )
        self.button = customtkinter.CTkButton(
            self.main_frame,
            text='Query LLMs',
            command=self.button_callback,
            height=42,
            corner_radius=14,
        )
        self.button.grid(row=2, column=0, padx=18, pady=(0, 18), sticky='ew')

        self.refresh_history_sidebar()
        self.check_queue_for_updates()

    def button_callback(self):
        if self._loaded_history_query is not None:
            return

        query = self.queryInput.get()
        if not query:
            return

        if self._llm_handler is None:
            print('No LLM handler provided.')
            return

        self._loaded_history_query = None
        self._set_query_button_enabled(True)
        apis = self._llm_handler._apis
        query_id = str(uuid4())
        with self._results_lock:
            self._latest_query_results = {}
        self._create_cards([
            {
                'name': getattr(api, '_name', None) or f'Response {index + 1}',
                'score': None,
            }
            for index, api in enumerate(apis)
        ])

        query_thread = threading.Thread(
            target=self.query_worker, args=(query, query_id), daemon=True
        )
        query_thread.start()

    def show_new_query_mode(self):
        '''
        Return to the blank query composer and clear any loaded history view
        '''
        self._loaded_history_query = None
        self._set_query_button_enabled(True)
        self._clear_cards()
        self.queryInput.delete(0, 'end')
        self.queryInput.focus_set()

    def refresh_history_sidebar(self):
        '''
        Reload the sidebar with queries stored in the database
        '''
        for widget in self.history_frame.winfo_children():
            widget.destroy()
        self._history_buttons.clear()

        if self._database_manager is None:
            empty_state = customtkinter.CTkLabel(
                self.history_frame,
                text='No database available.',
                anchor='w',
            )
            empty_state.pack(fill='x', padx=8, pady=8)
            return

        queries = self._database_manager.fetch_queries()
        if not queries:
            empty_state = customtkinter.CTkLabel(
                self.history_frame,
                text='No saved queries yet.',
                anchor='w',
            )
            empty_state.pack(fill='x', padx=8, pady=8)
            return

        for query_id, query, timestamp, top_score in queries:
            preview = self._truncate_query(query)
            score_text = f'Top Score: {top_score}' if top_score is not None else 'Top Score: n/a'
            button_text = f'{preview}\n{timestamp}\n{score_text}'
            button = customtkinter.CTkButton(
                self.history_frame,
                text=button_text,
                command=lambda qid=query_id, q=query: self.load_query_from_history(
                    qid, q),
                anchor='w',
                corner_radius=12,
                height=72,
            )
            button.pack(fill='x', padx=8, pady=6)
            self._history_buttons.append(button)

    def load_query_from_history(self, query_id, query):
        '''
        Load a previously saved query into the card-based view
        '''
        if self._database_manager is None:
            return

        responses = self._database_manager.fetch_responses_for_query(
            query_id, query)
        if not responses:
            return

        self._loaded_history_query = query
        self._set_query_button_enabled(False)
        self.queryInput.delete(0, 'end')
        self.queryInput.insert(0, query)
        self._create_cards(
            [
                {
                    'name': response['api_name'],
                    'text': response['response'],
                    'score': response.get('score'),
                }
                for response in responses
            ]
        )

    def _set_query_button_enabled(self, enabled):
        state = 'normal' if enabled else 'disabled'
        self.button.configure(state=state)

    def _truncate_query(self, query, max_length=52):
        clean_query = ' '.join(query.split())
        if len(clean_query) <= max_length:
            return clean_query
        return clean_query[: max_length - 3] + '...'

    def _clear_cards(self):
        for widget in self.responses_frame.winfo_children():
            widget.destroy()
        self._textDisplays.clear()

    def _ordinal(self, value):
        if 10 <= value % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(value % 10, 'th')
        return f'{value}{suffix}'

    def _rank_style(self, rank):
        if rank == 1:
            return {
                'border': '#D4AF37',
                'rank_bg': '#F59E0B',
                'rank_fg': '#111827',
            }
        if rank == 2:
            return {
                'border': '#C0C0C0',
                'rank_bg': '#94A3B8',
                'rank_fg': '#111827',
            }
        if rank == 3:
            return {
                'border': '#CD7F32',
                'rank_bg': '#B45309',
                'rank_fg': '#F9FAFB',
            }
        return {
            'border': '#E5E7EB',
            'rank_bg': '#6B7280',
            'rank_fg': '#F9FAFB',
        }

    def _create_cards(self, cards):
        '''
        Create cards in the UI for the provided card data
        '''
        self._clear_cards()

        cards_to_render = list(cards)
        if cards_to_render and all(card.get('score') is not None for card in cards_to_render):
            cards_to_render.sort(
                key=lambda card: card.get('score', 0), reverse=True
            )

        for index, card_data in enumerate(cards_to_render):
            score = card_data.get('score')
            rank = index + 1 if score is not None else None
            style = self._rank_style(rank) if rank else self._rank_style(99)

            card = customtkinter.CTkFrame(
                self.responses_frame,
                corner_radius=18,
                border_width=1,
                border_color=(style['border'], style['border']),
                fg_color=('#FFFFFF', '#111827'),
            )
            card.grid(row=0, column=index, padx=8, pady=8, sticky='nsew')
            card.grid_columnconfigure(0, weight=1)

            title = customtkinter.CTkLabel(
                card,
                text=card_data['name'],
                font=('Segoe UI Semibold', 14),
                anchor='w',
            )
            title.grid(row=0, column=0, padx=16, pady=(14, 8), sticky='ew')

            rank_text = f"Ranked {self._ordinal(rank)}" if rank else 'Ranking pending'
            rank_label = customtkinter.CTkLabel(
                card,
                text=rank_text,
                corner_radius=10,
                fg_color=style['rank_bg'],
                text_color=style['rank_fg'],
                font=('Segoe UI Semibold', 12),
                padx=10,
                pady=4,
            )
            rank_label.grid(row=1, column=0, padx=16, pady=(0, 6), sticky='w')

            score_text = f'Score: {score}' if score is not None else 'Score: ...'
            score_label = customtkinter.CTkLabel(
                card,
                text=score_text,
                anchor='w',
                font=('Segoe UI', 12),
                text_color=('#1F2937', '#E5E7EB'),
            )
            score_label.grid(row=2, column=0, padx=16,
                             pady=(0, 8), sticky='ew')

            self._textDisplays[index] = textDisplay(
                card, width=340, height=540)
            self._textDisplays[index].grid(
                row=3, column=0, padx=16, pady=(0, 16), sticky='nsew'
            )

            if card_data.get('text'):
                self._textDisplays[index].add_text(card_data['text'])

    def check_queue_for_updates(self):
        '''Runs on the MAIN thread.'''
        try:
            while True:
                data = self.response_queue.get_nowait()
                card_index = data['index']
                chunk = data['text']
                self._textDisplays[card_index].append_text(chunk)

        except queue.Empty:
            pass
        finally:
            self.after(50, self.check_queue_for_updates)

    def query_worker(self, query, query_id):
        '''
        Worker function to query the LLM APIs and update the UI with the responses
        '''
        if self._llm_handler is None:
            return
        apis = self._llm_handler._apis
        workers = []

        for index, api in enumerate(apis):
            worker = threading.Thread(
                target=self._api_worker,
                args=(api, query_id, query, index),
                daemon=True,
            )
            worker.start()
            workers.append(worker)

        for worker in workers:
            worker.join()

        if self._latest_query_results:
            self.after(0, self._render_ranked_cards_when_ready)

        if self._database_manager is not None:
            self.after(0, self.refresh_history_sidebar)

    def _render_ranked_cards_when_ready(self):
        if not self.response_queue.empty():
            self.after(50, self._render_ranked_cards_when_ready)
            return

        with self._results_lock:
            ranked_cards = [
                data for _, data in sorted(self._latest_query_results.items())
            ]
        self._create_cards(ranked_cards)

    def _api_worker(self, api, query_id, query, index):
        '''
        Read the response stream from one API and add it to the queue
        '''
        try:
            response = api.query_stream(query)
            full_response = ''

            if isinstance(response, str) or response is None:
                if response:
                    full_response = response
                    self.response_queue.put({'index': index, 'text': response})
            else:
                for chunk in response:
                    full_response += chunk
                    self.response_queue.put({'index': index, 'text': chunk})

            score = None
            if full_response:
                score = self._ranker.rank_response(query, full_response)

            with self._results_lock:
                self._latest_query_results[index] = {
                    'name': getattr(api, '_name', f'Response {index + 1}'),
                    'text': full_response,
                    'score': score,
                }

            if full_response and self._database_manager and hasattr(api, '_name'):
                self._database_manager.insert_response(
                    query_id, query, full_response, api._name, score)

        except Exception as e:
            error_text = f'\n[Error: {e}]'
            self.response_queue.put({'index': index, 'text': error_text})
            with self._results_lock:
                self._latest_query_results[index] = {
                    'name': getattr(api, '_name', f'Response {index + 1}'),
                    'text': error_text,
                    'score': 0,
                }
            if self._database_manager and hasattr(api, '_name'):
                self._database_manager.insert_response(
                    query_id, query, error_text, api._name, 0)


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


class DatabaseManager:
    '''
    A class for managing the SQLite database, including creating tables and inserting/querying data
    '''

    def __init__(self, db_name=DB_NAME):
        self.db_name = db_name
        self._create_tables()

    def _create_tables(self):
        '''
        Create the necessary tables in the database if they don't already exist
        '''
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_id TEXT,
                    query TEXT NOT NULL,
                    response TEXT NOT NULL,
                    api_name TEXT NOT NULL,
                    score INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Backward-compatible migration for existing DBs created before query_id existed.
            cursor.execute("PRAGMA table_info(responses)")
            column_names = [row[1] for row in cursor.fetchall()]
            if 'query_id' not in column_names:
                cursor.execute(
                    "ALTER TABLE responses ADD COLUMN query_id TEXT")
            if 'score' not in column_names:
                cursor.execute(
                    "ALTER TABLE responses ADD COLUMN score INTEGER")

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_responses_query_id
                ON responses(query_id)
            ''')
            conn.commit()

    def fetch_queries(self):
        '''
        Return query runs ordered by most recent response first
        '''
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    COALESCE(query_id, 'legacy:' || query) AS run_id,
                    query,
                    MAX(timestamp) AS latest_timestamp,
                    MAX(score) AS top_score
                FROM responses
                GROUP BY run_id, query
                ORDER BY latest_timestamp DESC
            ''')
            return cursor.fetchall()

    def fetch_responses_for_query(self, query_id, query):
        '''
        Return all stored responses for a query run in insertion order
        '''
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            if query_id.startswith('legacy:'):
                cursor.execute('''
                    SELECT api_name, response, timestamp
                    FROM responses
                    WHERE query = ? AND query_id IS NULL
                    ORDER BY id ASC
                ''', (query,))
            else:
                cursor.execute('''
                    SELECT api_name, response, timestamp, score
                    FROM responses
                    WHERE query_id = ?
                    ORDER BY id ASC
                ''', (query_id,))
            rows = cursor.fetchall()
            return [
                {
                    'api_name': row[0],
                    'response': row[1],
                    'timestamp': row[2],
                    'score': row[3] if len(row) > 3 else None,
                }
                for row in rows
            ]

    def insert_response(self, query_id, query, response, api_name, score=None):
        '''
        Insert a new response into the database
        '''
        with sqlite3.connect(self.db_name) as conn:
            timestamp = datetime.now().isoformat()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO responses (query_id, query, response, api_name, score, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (query_id, query, response, api_name, score, timestamp))
            conn.commit()


database_manager = DatabaseManager()
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
app = App(llm_handler=main_llm_handler, database_manager=database_manager)
app.mainloop()
