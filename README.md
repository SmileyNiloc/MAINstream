# MAINstream

A desktop app that runs the same prompt against several LLMs in parallel, scores each response with a local judge, and surfaces a live comparative ranking that refines itself as responses stream in.

## What it does

You type a query once. mAInstream fires it at every configured model concurrently, streams each model's response into its own card, scores each completed response on a 1–10 scale using a local Ollama judge, and then asks the same judge to comparatively rank the responses against one another. The comparison runs again every time a new response finishes, so a late-arriving answer that's clearly better can leapfrog earlier ones without you having to re-run anything.

Failed responses (rate limits, 4xx, network errors) are kept on screen for debugging but are excluded from the ranking, so two successful responses among five errors get ranked 1st and 2nd — not 5th and 7th.

## Features

- **Parallel querying** of any number of LLM providers from one prompt
- **Streaming** responses, chunk-by-chunk, into each card
- **Per-response scoring** (1–10) by a local Ollama judge
- **Real-time comparative ranking** that re-runs after every completion, with coalescing so simultaneous completions don't pile up judge calls
- **Error-aware display** — failed responses keep their card but don't occupy rank slots
- **Composite sort key** — comparative rank breaks score ties automatically; score breaks comparative-rank ties when applicable
- **Optional system prompt** sent to every model
- **History sidebar** backed by SQLite — every run is persisted and can be re-opened
- **Markdown rendering** in every response card

## Architecture

```
main.py                 # entry point: loads .env, wires APIs, starts the app
src/
  app.py                # CustomTkinter GUI, threading, ranking orchestration
  dbmanager.py          # SQLite layer (mainstream.db)
  llmapis.py            # llmApi base class + Gemini / OpenRouter / OpenAI adapters
  rank.py               # Ranker — scoring and comparative ranking via local Ollama
  textdisplay.py        # Markdown-rendering response card
```

Each LLM provider is an `llmApi` subclass exposing `query()` and `query_stream()`. `llmApiHandler` holds the list and enforces a minimum delay between any two outbound requests. Adding a new provider is one class.

The `Ranker` talks to a local Ollama instance through the OpenAI-compatible API on `localhost:11434`. It exposes `rank_response(query, response) -> int` and `compare_responses(query, [(id, text, score), ...]) -> [(rank, id), ...]`. The score is fed back into the comparison prompt so the judge's rank is consistent with the scores it just gave; if Ollama is unreachable, comparison falls back to score-descending order.

## How ranking works

There are two layers, and they're designed to agree:

**Score** is independent — the judge sees one response at a time and rates it 1–10 on accuracy, clarity, completeness, and conciseness. This happens inside each API worker thread, immediately after the response finishes streaming, gated by a shared lock so only one judge call runs at a time.

**Comparative rank** is side-by-side. Once a response has a score, the app triggers a comparative-ranking pass that snapshots every currently-successful response (id, text, score) and asks the judge to assign a unique rank to each. The judge is told to treat each response's prior score as a strong signal but can deviate when side-by-side comparison reveals a clear reason.

Triggers are coalesced. If a pass is already running, the trigger just flips a "pending" flag and returns; when the in-flight pass finishes, it runs one more if the flag was set. So a burst of N completions becomes at most one in-flight call plus one queued rerun — not N sequential judge calls.

The composite sort key in the UI is `(score_desc, comparative_rank_asc)`, swapped to `(comparative_rank_asc, score_desc)` when the dropdown is set to "Comparative Rank". Missing values sort last but never disable the sort.

## Setup

### Requirements

- Python 3.10+
- [Ollama](https://ollama.com) running locally with a judge model pulled
- API keys for the providers you want to use

### Install dependencies

```bash
pip install customtkinter python-dotenv openai google-genai ctk-markdown
```

### Pull the judge model

The default judge is `qwen2.5:7b` (see `Ranker.__init__` in `src/rank.py`):

```bash
ollama pull qwen2.5:7b
ollama serve   # if not already running
```

Any Ollama-served model works — change the `model` argument to `Ranker(...)` to swap.

### Configure API keys

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_key
OPEN_ROUTER_API_KEY=your_openrouter_key
OPENAI_API_KEY=your_openai_key       # optional, OpenAI adapter is wired but commented in main.py
```

A Gemini key is required because the default config registers a Gemini API and the ranker is initialised against it. The OpenRouter models in the default config are all `:free` tier — get a free key at openrouter.ai.

### Run

```bash
python main.py
```

## Configuring which models to query

Edit `main.py`. The default loadout is:

```python
main_llm_handler.add_api(geminiApi(GEMINI_API_KEY, name="Gemini API"))

open_router_models = {
    "Gemini Gemma 4 31B":   "google/gemma-4-31b-it:free",
    "NVIDIA nemotron":      "nvidia/nemotron-3-super-120b-a12b:free",
    "Poolside Laguna M.1":  "poolside/laguna-m.1:free",
    "Owl Alpha":            "openrouter/owl-alpha",
    "Baidu Qianfan: CoBuddy": "baidu/cobuddy:free",
    "OpenAI: gpt-oss-120b": "openai/gpt-oss-120b:free",
}
```

Add or remove entries to taste. Any OpenRouter model id works; drop `:free` to use paid models. Custom providers just need a new `llmApi` subclass implementing `query()` and optionally `query_stream()`.

## Database

mAInstream stores everything in a single SQLite file (`mainstream.db`, created on first run) with one `responses` table:

| column            | type     | notes                                       |
| ----------------- | -------- | ------------------------------------------- |
| `id`              | INTEGER  | primary key                                 |
| `query_id`        | TEXT     | UUID grouping responses from one run        |
| `query`           | TEXT     | the user's prompt                           |
| `response`        | TEXT     | the model's full response                   |
| `api_name`        | TEXT     | provider/model label                        |
| `score`           | INTEGER  | 1–10, `NULL` for errors                     |
| `comparative_rank`| INTEGER  | 1 = best, assigned by the judge             |
| `timestamp`       | DATETIME | inserted when the response is saved         |

Backward-compatible migration runs at startup, so adding the app to a folder with an older `mainstream.db` won't break it.

## Usage notes

- **Enter** submits the query; **Shift+Enter** inserts a newline.
- The **System Prompt** panel is collapsed by default — click the header to expand it.
- The sidebar lists past runs newest-first; clicking one re-opens the cards with their saved responses, scores, and comparative ranks.
- Sort by **Score** (default) or **Comparative Rank** via the dropdown above the query input.

## Known limitations

- The Ollama judge is a hard dependency. Without it, `Ranker` falls back to a neutral score of 5 and ranks by score descending — usable but not interesting.
- Comparative ranking re-runs after every completion. On local Ollama this is fine; if you point `Ranker` at a paid API, add throttling.
- Free-tier providers will rate-limit you quickly under load — errors will surface as cards with red `Error` badges and detailed payloads inside.
