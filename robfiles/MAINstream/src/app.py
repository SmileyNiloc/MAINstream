import customtkinter
import threading
import time
from uuid import uuid4
from src.rank import Ranker
from src.textdisplay import textDisplay


class App(customtkinter.CTk):
    def __init__(self, llm_handler=None, database_manager=None):
        super().__init__()

        self._llm_handler = llm_handler
        self._database_manager = database_manager
        self._loaded_history_query = None
        self._ranker = Ranker()          # configured later via _init_ranker()
        self._latest_query_results = {}
        self._results_lock = threading.Lock()
        self._current_card_data = []
        self._query_in_progress = False
        self._ranker_lock = threading.Lock()
        # Incremental comparative ranking state — see _trigger_comparative_rerank.
        self._compare_state_lock = threading.Lock()
        self._compare_running = False
        self._compare_pending = False
        self._current_query = None
        self._current_query_id = None

        self.title('MAINstream')
        self.geometry(f'{1520}x{1120}')
        self.bind('<Configure>', self._on_window_resize)
        self._resize_job = None
        self._card_frames = []

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.current_card_index = 0
        self._responses = []
        self._textDisplays = {}
        self._history_buttons = []

        # Sidebar
        self.sidebar_frame = customtkinter.CTkFrame(
            self,
            corner_radius=18,
            border_width=1,
            border_color=('#D1D5DB', '#374151'),
            fg_color=('#F8FAFC', '#111827'),
            width=340,
        )
        self.sidebar_frame.grid(
            row=0, column=0, padx=(28, 14), pady=28, sticky='nsew'
        )
        self.sidebar_frame.grid_columnconfigure(0, weight=1)
        self.sidebar_frame.grid_rowconfigure(3, weight=1)

        sidebar_title = customtkinter.CTkLabel(
            self.sidebar_frame,
            text='Query history',
            font=('Segoe UI Semibold', 18),
            anchor='w',
        )
        sidebar_title.grid(row=0, column=0, padx=18, pady=(18, 10), sticky='ew')

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

        # Main panel
        self.main_frame = customtkinter.CTkFrame(
            self,
            corner_radius=18,
            border_width=1,
            border_color=('#D1D5DB', '#374151'),
            fg_color=('#F8FAFC', '#111827'),
        )
        self.main_frame.grid(
            row=0, column=1, padx=(14, 28), pady=28, sticky='nsew'
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
            row=0, column=0, padx=22, pady=(22, 14), sticky='nsew'
        )

        # System prompt (collapsible)
        self._system_prompt_visible = False

        self._system_prompt_toggle = customtkinter.CTkButton(
            self.main_frame,
            text='~  System Prompt',
            command=self._toggle_system_prompt,
            height=32,
            corner_radius=10,
            fg_color='transparent',
            text_color=('#1D4ED8', '#60A5FA'),
            hover_color=('#EFF6FF', '#1E3A5F'),
            anchor='w',
            font=('Segoe UI Semibold', 13),
        )
        self._system_prompt_toggle.grid(
            row=1, column=0, padx=18, pady=(0, 0), sticky='w'
        )

        self._system_prompt_frame = customtkinter.CTkFrame(
            self.main_frame,
            fg_color='transparent',
        )
        # Not gridded yet, shown only when expanded

        system_prompt_label = customtkinter.CTkLabel(
            self._system_prompt_frame,
            text='System prompt (sent to every model before the query):',
            anchor='w',
            font=('Segoe UI', 12),
            text_color=('#6B7280', '#9CA3AF'),
        )
        system_prompt_label.pack(fill='x', padx=0, pady=(0, 4))

        self.systemPromptInput = customtkinter.CTkTextbox(
            self._system_prompt_frame,
            height=90,
            corner_radius=12,
            border_width=1,
            border_color=('#D1D5DB', '#374151'),
            wrap='word',
            font=('Segoe UI', 13),
        )
        self.systemPromptInput.pack(fill='x', padx=0, pady=(0, 6))

        # Query input
        self.queryInput = customtkinter.CTkTextbox(
            self.main_frame,
            height=72,
            corner_radius=14,
            border_width=1,
            border_color=('#D1D5DB', '#374151'),
            wrap='word',
            font=('Segoe UI', 14),
        )
        self.queryInput.grid(
            row=3, column=0, padx=18, pady=(6, 8), sticky='ew'
        )
        # Bind Enter to submit, Shift+Enter to newline
        self.queryInput.bind('<Return>', self._on_query_enter)
        self.queryInput.bind('<Shift-Return>', lambda e: None)  # allow newline

        self.button = customtkinter.CTkButton(
            self.main_frame,
            text='Query LLMs',
            command=self.button_callback,
            height=48,
            corner_radius=14,
        )
        self.button.grid(row=4, column=0, padx=18, pady=(0, 18), sticky='ew')

        # Sorting control
        self._sort_by = 'score'
        self.sort_option = customtkinter.CTkOptionMenu(
            self.main_frame,
            values=['Score', 'Comparative Rank'],
            command=self._on_sort_option_change,
        )
        self.sort_option.set('Score')
        self.sort_option.grid(row=5, column=0, padx=18, pady=(0, 12), sticky='e')

        self.refresh_history_sidebar()
        self._init_ranker()

    # Ranker initialisation

    def _init_ranker(self):
        '''Wire the Ranker to the first Gemini API found in the handler.'''
        if self._llm_handler is None:
            return
        from src.llmapis import geminiApi
        for api in self._llm_handler._apis:
            if isinstance(api, geminiApi):
                self._ranker = Ranker(gemini_api_key=api._api_key)
                print('[App] Ranker initialised with Gemini.')
                return
        print('[App] Warning: No Gemini API found; Ranker will use fallback scores.')

    # System prompt toggle

    def _toggle_system_prompt(self):
        self._system_prompt_visible = not self._system_prompt_visible
        if self._system_prompt_visible:
            self._system_prompt_toggle.configure(text='▼  System Prompt')
            self._system_prompt_frame.grid(
                row=2, column=0, padx=18, pady=(4, 0), sticky='ew'
            )
        else:
            self._system_prompt_toggle.configure(text='▶  System Prompt')
            self._system_prompt_frame.grid_forget()

    def _get_system_prompt(self):
        '''Return stripped system prompt text, or None if empty.'''
        text = self.systemPromptInput.get('1.0', 'end').strip()
        return text if text else None

    # Query entry helpers

    def _on_query_enter(self, event):
        '''Submit on plain Enter; Shift+Enter lets the default newline happen.'''
        if not (event.state & 0x1):   # Shift not held
            self.button_callback()
            return 'break'            # suppress the newline

    def _get_query_text(self):
        return self.queryInput.get('1.0', 'end').strip()

    def _clear_query_input(self):
        self.queryInput.delete('1.0', 'end')

    def _set_query_input(self, text):
        self._clear_query_input()
        self.queryInput.insert('1.0', text)

    # Window resize

    def _on_window_resize(self, event):
        if event.widget is not self:
            return
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(100, self._update_card_widths)

    def _update_card_widths(self):
        self._resize_job = None
        if not hasattr(self, '_card_frames') or not self._card_frames:
            return
        try:
            available_width = self.responses_frame._parent_canvas.winfo_width()
        except AttributeError:
            available_width = self.responses_frame.winfo_width()
        if available_width <= 1:
            available_width = self.winfo_width() - 400
        card_count = len(self._card_frames)
        target_width = int((available_width / card_count) - 34)
        target_width = max(400, target_width)
        for card in self._card_frames:
            if card.winfo_exists():
                card.configure(width=target_width)
                try:
                    card.grid_propagate(False)
                except Exception:
                    pass
        try:
            self.responses_frame.update_idletasks()
            canvas = getattr(self.responses_frame, '_parent_canvas', None)
            if canvas is not None:
                canvas.configure(scrollregion=canvas.bbox('all'))
        except Exception:
            pass

    # Button / query dispatch

    def button_callback(self):
        if self._loaded_history_query is not None:
            return
        query = self._get_query_text()
        if not query:
            return
        if self._llm_handler is None:
            print('No LLM handler provided.')
            return

        system_prompt = self._get_system_prompt()

        self._loaded_history_query = None
        self._set_query_button_enabled(True)
        apis = self._llm_handler._apis
        query_id = str(uuid4())
        # Stash for the background compare loop, which needs both to call
        # the ranker and to update the right rows in the DB.
        self._current_query = query
        self._current_query_id = query_id
        self._query_in_progress = True
        with self._results_lock:
            self._latest_query_results = {
                index: {
                    'name': getattr(api, '_name', None) or f'Response {index + 1}',
                    'score': None,
                    'text': None,
                    'comparative_rank': None,
                }
                for index, api in enumerate(apis)
            }

        self._render_current_cards()

        query_thread = threading.Thread(
            target=self.query_worker,
            args=(query, query_id, system_prompt),
            daemon=True,
        )
        query_thread.start()

    def show_new_query_mode(self):
        self._loaded_history_query = None
        self._set_query_button_enabled(True)
        self._clear_cards()
        self._clear_query_input()
        self.queryInput.focus_set()

    def _on_sort_option_change(self, value):
        self._sort_by = 'comparative_rank' if value == 'Comparative Rank' else 'score'
        with self._results_lock:
            cards = [data for _, data in sorted(self._latest_query_results.items())]
        self._create_cards(cards)

    # History sidebar

    def refresh_history_sidebar(self):
        for widget in self.history_frame.winfo_children():
            widget.destroy()
        self._history_buttons.clear()

        if self._database_manager is None:
            customtkinter.CTkLabel(
                self.history_frame, text='No database available.', anchor='w'
            ).pack(fill='x', padx=8, pady=8)
            return

        queries = self._database_manager.fetch_queries()
        if not queries:
            customtkinter.CTkLabel(
                self.history_frame, text='No saved queries yet.', anchor='w'
            ).pack(fill='x', padx=8, pady=8)
            return

        for query_id, query, timestamp, top_score in queries:
            preview = self._truncate_query(query)
            score_text = f'Top Score: {top_score}' if top_score is not None else 'Top Score: n/a'
            button_text = f'{preview}\n{timestamp}\n{score_text}'
            button = customtkinter.CTkButton(
                self.history_frame,
                text=button_text,
                command=lambda qid=query_id, q=query: self.load_query_from_history(qid, q),
                anchor='w',
                corner_radius=12,
                height=86,
            )
            button.pack(fill='x', padx=8, pady=6)
            self._history_buttons.append(button)

    def load_query_from_history(self, query_id, query):
        if self._database_manager is None:
            return
        responses = self._database_manager.fetch_responses_for_query(query_id, query)
        if not responses:
            return
        self._loaded_history_query = query
        self._set_query_button_enabled(False)
        self._set_query_input(query)
        self._current_card_data = [
            {
                'name': response['api_name'],
                'text': response['response'],
                'score': response.get('score'),
                'comparative_rank': response.get('comparative_rank'),
            }
            for response in responses
        ]
        self._create_cards(self._current_card_data)

    # Query workers

    def query_worker(self, query, query_id, system_prompt=None):
        '''Spawn one thread per API. Comparative ranking runs incrementally as
        each response completes (see _trigger_comparative_rerank) rather than
        in one big pass at the end. The final trigger here is a safety net.'''
        try:
            if self._llm_handler is None:
                return
            apis = self._llm_handler._apis
            workers = []
            for index, api in enumerate(apis):
                worker = threading.Thread(
                    target=self._api_worker,
                    args=(api, query_id, query, index, system_prompt),
                    daemon=True,
                )
                worker.start()
                workers.append(worker)
                # time.sleep(3.0)

            for worker in workers:
                worker.join()

            # Safety net: ensure one definitive compare with everything present.
            # If a per-response trigger is already running this is a no-op (coalesced).
            self._trigger_comparative_rerank()

            if self._latest_query_results:
                self.after(0, self._render_current_cards)

            if self._database_manager is not None:
                self.after(0, self.refresh_history_sidebar)
        finally:
            self._query_in_progress = False

    def _api_worker(self, api, query_id, query, index, system_prompt=None):
        '''
        Stream one API's response chunk-by-chunk, appending to the card live.
        Scoring happens after the full response is assembled.
        '''
        try:
            full_response = ''
            response = api.query_stream(query, system_prompt=system_prompt)

            if isinstance(response, str) or response is None:
                full_response = response or ''
                # with self._results_lock:
                self._latest_query_results[index]['text'] = full_response
                self.after(0, self._render_current_cards)
            else:
                # True streaming: yield chunks and push to UI incrementally
                for chunk in response:
                    full_response += chunk
                    # Snapshot for thread-safe UI update
                    snapshot = full_response
                    with self._results_lock:
                        self._latest_query_results[index]['text'] = snapshot
                    self.after(0, self._update_card_text, index, snapshot)

            score = None
            if full_response and not full_response.startswith('\n[Error'):
                with self._ranker_lock: # Ensure only one ranking happens at a time
                    score = self._ranker.rank_response(query, full_response)

            with self._results_lock:
                self._latest_query_results[index].update({
                    'name': getattr(api, '_name', f'Response {index + 1}'),
                    'api_name': getattr(api, '_name', f'Response {index + 1}'),
                    'text': full_response,
                    'score': score,
                })

            row_id = None
            if full_response and self._database_manager and hasattr(api, '_name'):
                row_id = self._database_manager.insert_response(
                    query_id, query, full_response, api._name, score
                )

            if row_id is not None:
                with self._results_lock:
                    self._latest_query_results[index]['id'] = row_id

            # Final render to update score badge
            self.after(0, self._render_current_cards)

            # Real-time comparative ranking: now that this response has a
            # score and id, ask the judge to re-rank every successful response
            # currently available. Coalesced so simultaneous completions
            # don't pile up calls.
            if score is not None:
                self._trigger_comparative_rerank()

        except Exception as e:
            error_text = f'\n[Error: {e}]'
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
                    query_id, query, error_text, api._name, 0
                )
                if row_id is not None:
                    with self._results_lock:
                        self._latest_query_results[index]['id'] = row_id
            self.after(0, self._render_current_cards)

    # Real-time comparative ranking

    def _trigger_comparative_rerank(self):
        '''Schedule a comparative re-ranking pass.

        Coalesces concurrent triggers: if a compare is already running, sets a
        pending flag so the in-flight pass re-checks on completion. A burst of
        completions becomes at most one extra compare after the current one.
        '''
        with self._compare_state_lock:
            if self._compare_running:
                self._compare_pending = True
                return
            self._compare_running = True

        threading.Thread(target=self._compare_loop, daemon=True).start()

    def _compare_loop(self):
        '''Run compare passes until no new triggers have arrived since the last one.'''
        try:
            while True:
                with self._compare_state_lock:
                    self._compare_pending = False
                try:
                    self._do_compare_once()
                except Exception as exc:
                    print(f'[App] Comparative rerank error: {exc}')
                with self._compare_state_lock:
                    if not self._compare_pending:
                        self._compare_running = False
                        return
        except Exception:
            # Make sure flags are released so future triggers still work.
            with self._compare_state_lock:
                self._compare_running = False
                self._compare_pending = False
            raise

    def _do_compare_once(self):
        '''Snapshot completed responses, ask the judge to rank them, write back.'''
        query = self._current_query
        query_id = self._current_query_id
        if not query:
            return

        with self._results_lock:
            snapshot = [dict(data) for _, data in sorted(self._latest_query_results.items())]

        successful = [
            (data.get('id'), data.get('text', ''), data.get('score'))
            for data in snapshot
            if data.get('text')
            and not data['text'].startswith('\n[Error')
            and data.get('score') is not None
            and data.get('id') is not None
        ]

        # Need at least two to actually compare. One response is trivially #1.
        if len(successful) < 2:
            if len(successful) == 1 and self._current_query_id == query_id:
                row_id = successful[0][0]
                with self._results_lock:
                    for result in self._latest_query_results.values():
                        if result.get('id') == row_id:
                            result['comparative_rank'] = 1
                            break
                if self._database_manager is not None:
                    self._database_manager.update_comparative_rank_by_id(row_id, 1)
                self.after(0, self._render_current_cards)
            return

        # Same Ollama backend as per-response scoring — serialize through the
        # ranker lock so we don't fire two judge calls at once.
        with self._ranker_lock:
            # The user may have started a new query while we were waiting on
            # the lock; bail out if the query changed.
            if self._current_query_id != query_id:
                return
            comparative_results = self._ranker.compare_responses(query, successful)

        if not comparative_results:
            return

        # Write back into the in-memory state and the DB.
        with self._results_lock:
            if self._current_query_id != query_id:
                return  # query changed mid-flight
            for rank_val, row_id in comparative_results:
                for result in self._latest_query_results.values():
                    if result.get('id') == row_id:
                        result['comparative_rank'] = rank_val
                        break

        if self._database_manager is not None:
            for rank_val, row_id in comparative_results:
                if row_id is not None:
                    self._database_manager.update_comparative_rank_by_id(row_id, rank_val)

        self.after(0, self._render_current_cards)

    # Card text streaming helper

    def _update_card_text(self, index, text):
        '''Append streamed text to an existing card without full re-render.'''
        display = self._textDisplays.get(index)
        if display is not None and display.winfo_exists():
            display.add_text(text)

    # Card rendering
    def _render_current_cards(self):
        with self._results_lock:
            cards = [
                dict(data) for _, data in sorted(self._latest_query_results.items())
            ]
        self._create_cards(cards)

    def _clear_cards(self):
        for widget in self.responses_frame.winfo_children():
            widget.destroy()
        self._textDisplays.clear()
        self._card_frames = []

    def _create_cards(self, cards):
        self._clear_cards()

        cards_to_render = list(cards)
        self._current_card_data = [dict(card) for card in cards_to_render]

        card_count = max(1, len(cards_to_render))

        try:
            available_width = self.responses_frame._parent_canvas.winfo_width()
        except AttributeError:
            available_width = self.responses_frame.winfo_width()

        if available_width <= 1:
            available_width = self.winfo_width() - 400

        target_width = int((available_width / card_count) - 34)
        target_width = max(400, target_width)

        # Partition errors out before sorting/ranking so they neither occupy
        # rank slots nor block the sort (which previously required *every*
        # card to have a score; one error with score=None disabled it).
        def _is_error_card(card):
            return (card.get('text') or '').startswith('\n[Error')

        non_error_cards = [c for c in cards_to_render if not _is_error_card(c)]
        error_cards = [c for c in cards_to_render if _is_error_card(c)]

        # Composite sort key: each key falls back to the other for ties, and
        # missing values sort last. This is how real-time comparative ranking
        # surfaces in the UI — same score, judge prefers gpt-oss over owl =>
        # gpt-oss moves to 1st automatically, no manual sort toggle needed.
        def _sort_key(card):
            score = card.get('score')
            comp = card.get('comparative_rank')
            score_key = -score if score is not None else 1  # higher score first
            comp_key = comp if comp is not None else 9999   # lower rank first
            if self._sort_by == 'comparative_rank':
                return (comp_key, score_key)
            return (score_key, comp_key)

        if non_error_cards:
            non_error_cards.sort(key=_sort_key)

        # Render successful responses first, errors at the end
        cards_to_render = non_error_cards + error_cards

        # Rank counter — only successful, scored responses consume a rank slot,
        # so two successes among five errors get 1st and 2nd, not 5th and 7th.
        ranked_position = 0
        for index, card_data in enumerate(cards_to_render):
            score = card_data.get('score')
            is_error = _is_error_card(card_data)
            if not is_error and score is not None:
                ranked_position += 1
                rank = ranked_position
            else:
                rank = None
            style = self._error_style() if is_error else (
                self._rank_style(rank) if rank else self._rank_style(99)
            )

            card = customtkinter.CTkFrame(
                self.responses_frame,
                corner_radius=22,
                border_width=1,
                border_color=(style['border'], style['border']),
                fg_color=('#FFFFFF', '#111827'),
                width=target_width,
            )
            self._card_frames.append(card)
            card.grid(row=0, column=index, padx=12, pady=12, sticky='nsew')
            card.grid_columnconfigure(0, weight=1)
            card.grid_rowconfigure(4, weight=1)
            try:
                card.grid_propagate(False)
            except Exception:
                pass

            title = customtkinter.CTkLabel(
                card,
                text=card_data['name'],
                font=('Segoe UI Semibold', 16),
                anchor='w',
            )
            title.grid(row=0, column=0, padx=20, pady=(18, 10), sticky='ew')

            if is_error:
                rank_text = 'Error'
            elif rank:
                rank_text = f"Ranked {self._ordinal(rank)}"
            else:
                rank_text = 'Ranking pending…'
            rank_label = customtkinter.CTkLabel(
                card,
                text=rank_text,
                corner_radius=12,
                fg_color=style['rank_bg'],
                text_color=style['rank_fg'],
                font=('Segoe UI Semibold', 13),
                padx=12,
                pady=6,
            )
            rank_label.grid(row=1, column=0, padx=20, pady=(0, 8), sticky='w')

            score_text = f'Score: {score}/10' if score is not None else 'Score: '
            score_label = customtkinter.CTkLabel(
                card,
                text=score_text,
                anchor='w',
                font=('Segoe UI', 13),
                text_color=('#1F2937', '#E5E7EB'),
            )
            score_label.grid(row=2, column=0, padx=20, pady=(0, 4), sticky='ew')

            comp_rank = card_data.get('comparative_rank')
            comp_text = f'Comparative Rank: {comp_rank}' if comp_rank is not None else 'Comparative Rank: '
            comp_label = customtkinter.CTkLabel(
                card,
                text=comp_text,
                anchor='w',
                font=('Segoe UI', 13),
                text_color=('#1F2937', '#E5E7EB'),
            )
            comp_label.grid(row=3, column=0, padx=20, pady=(0, 10), sticky='ew')

            self._textDisplays[index] = textDisplay(card, width=10, height=10)
            self._textDisplays[index].grid(
                row=4, column=0, padx=20, pady=(0, 20), sticky='nsew'
            )
            self.responses_frame.grid_rowconfigure(0, weight=1)
            self.responses_frame.grid_columnconfigure(index, weight=1, minsize=400)

            if card_data.get('text'):
                self._textDisplays[index].add_text(card_data['text'])

    # Utility

    def _set_query_button_enabled(self, enabled):
        state = 'normal' if enabled else 'disabled'
        self.button.configure(state=state)

    def _truncate_query(self, query, max_length=52):
        clean_query = ' '.join(query.split())
        if len(clean_query) <= max_length:
            return clean_query
        return clean_query[:max_length - 3] + '...'

    def _ordinal(self, value):
        if 10 <= value % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(value % 10, 'th')
        return f'{value}{suffix}'

    def _rank_style(self, rank):
        if rank == 1:
            return {'border': '#D4AF37', 'rank_bg': '#F59E0B', 'rank_fg': '#111827'}
        if rank == 2:
            return {'border': '#C0C0C0', 'rank_bg': '#94A3B8', 'rank_fg': '#111827'}
        if rank == 3:
            return {'border': '#CD7F32', 'rank_bg': '#B45309', 'rank_fg': '#F9FAFB'}
        return {'border': '#E5E7EB', 'rank_bg': '#6B7280', 'rank_fg': '#F9FAFB'}

    def _error_style(self):
        return {'border': '#EF4444', 'rank_bg': '#EF4444', 'rank_fg': '#FFFFFF'}