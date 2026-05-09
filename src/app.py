import customtkinter
import threading
import queue
from uuid import uuid4
from dotenv import load_dotenv
import os
from src.rank import Ranker
from src.textdisplay import textDisplay


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

        # Sorting control: choose between Score and Comparative Rank
        self._sort_by = 'score'
        self.sort_option = customtkinter.CTkOptionMenu(
            self.main_frame,
            values=['Score', 'Comparative Rank'],
            command=self._on_sort_option_change,
        )
        self.sort_option.set('Score')
        self.sort_option.grid(row=3, column=0, padx=18,
                              pady=(0, 12), sticky='e')

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

    def _on_sort_option_change(self, value):
        '''Handle sort option changes from the UI.'''
        self._sort_by = 'comparative_rank' if value == 'Comparative Rank' else 'score'
        with self._results_lock:
            cards = [data for _, data in sorted(
                self._latest_query_results.items())]
        self._create_cards(cards)

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
                    'comparative_rank': response.get('comparative_rank'),
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
        # Sort depending on chosen mode if all cards have the required value
        if self._sort_by == 'comparative_rank' and cards_to_render and all(
            card.get('comparative_rank') is not None for card in cards_to_render
        ):
            cards_to_render.sort(
                key=lambda card: card.get('comparative_rank', 9999))
        elif cards_to_render and all(card.get('score') is not None for card in cards_to_render):
            cards_to_render.sort(
                key=lambda card: card.get('score', 0), reverse=True)

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

            comp_rank = card_data.get('comparative_rank')
            comp_text = f'Comparative Rank: {comp_rank}' if comp_rank is not None else 'Comparative Rank: ...'
            comp_label = customtkinter.CTkLabel(
                card,
                text=comp_text,
                anchor='w',
                font=('Segoe UI', 12),
                text_color=('#1F2937', '#E5E7EB'),
            )
            comp_label.grid(row=3, column=0, padx=16, pady=(0, 8), sticky='ew')

            self._textDisplays[index] = textDisplay(
                card, width=340, height=540)
            self._textDisplays[index].grid(
                row=4, column=0, padx=16, pady=(0, 16), sticky='nsew'
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

        with self._results_lock:
            completed_results = [
                data for _, data in sorted(self._latest_query_results.items())
            ]

        # Build list of (row_id, text) for comparison so the comparator can
        # return (rank, row_id) tuples which can be written back to exact DB rows.
        responses_for_comparison = [
            (item.get('id'), item.get('text', '')) for item in completed_results
        ]

        comparative_results = self._ranker.compare_responses(
            query,
            responses_for_comparison,
        )

        # comparative_results is expected as list of (rank, row_id)
        if comparative_results:
            for rank_val, row_id in comparative_results:
                # Update in-memory representation
                for result in completed_results:
                    if result.get('id') == row_id:
                        result['comparative_rank'] = rank_val
                        break

                # Persist to DB by row id if available
                if self._database_manager is not None and row_id is not None:
                    self._database_manager.update_comparative_rank_by_id(
                        row_id, rank_val
                    )

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
                    'api_name': getattr(api, '_name', f'Response {index + 1}'),
                    'text': full_response,
                    'score': score,
                    'id': None,
                }

            row_id = None
            if full_response and self._database_manager and hasattr(api, '_name'):
                row_id = self._database_manager.insert_response(
                    query_id, query, full_response, api._name, score)

            if row_id is not None:
                with self._results_lock:
                    self._latest_query_results[index]['id'] = row_id

        except Exception as e:
            error_text = f'\n[Error: {e}]'
            self.response_queue.put({'index': index, 'text': error_text})
            with self._results_lock:
                self._latest_query_results[index] = {
                    'name': getattr(api, '_name', f'Response {index + 1}'),
                    'api_name': getattr(api, '_name', f'Response {index + 1}'),
                    'text': error_text,
                    'score': 0,
                    'id': None,
                }
            if self._database_manager and hasattr(api, '_name'):
                row_id = self._database_manager.insert_response(
                    query_id, query, error_text, api._name, 0)
                if row_id is not None:
                    with self._results_lock:
                        self._latest_query_results[index]['id'] = row_id
