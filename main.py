import logging
import os
from datetime import datetime
from dotenv import load_dotenv
from src.app import App
from src.dbmanager import DatabaseManager
from src.llmapis import llmApiHandler, geminiApi, openRouterApi, ollamaLocalApi
from src.rank import Ranker
from src.synthesize import Synthesizer
load_dotenv()

logs_dir = "logs"
os.makedirs(logs_dir, exist_ok=True)
log_file = os.path.join(
    logs_dir, f"mainstream_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(),
    ],
    force=True,
)

logging.getLogger().handlers[1].setLevel(logging.INFO)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPEN_ROUTER_API_KEY = os.getenv("OPEN_ROUTER_API_KEY")

DB_NAME = "mainstream.db"


database_manager = DatabaseManager()
main_llm_handler = llmApiHandler()
if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY not found. Add it to .env as GEMINI_API_KEY=... or export it in your shell."
    )
main_llm_handler.add_api(geminiApi(GEMINI_API_KEY, name="Gemini API"))

# Uncomment to add a local Ollama instance
main_llm_handler.add_api(ollamaLocalApi(
    name="Ollama 3 Local", model="llama3", url="http://localhost:11434/v1"))

open_router_models = {
    "Gemini Gemma 4 31B": ["google/gemma-4-31b-it:free", "google/gemma-4-26b-a4b-it:free"],
    # "NVIDIA nemotron": "nvidia/nemotron-3-super-120b-a12b:free",
    # "Poolside Laguna M.1": "poolside/laguna-m.1:free",
    "Owl Alpha": "openrouter/owl-alpha",
    "Inclusion AI": "inclusionai/ring-2.6-1t:free",
    # "Baidu Qianfan: CoBuddy": "baidu/cobuddy:free",
    "OpenAI: gpt-oss-120b": "openai/gpt-oss-120b:free",
    #    "Anthropic: Claude Haiku 4.5": "anthropic/claude-haiku-4.5" # This one is not free

}

for model_name, model_id in open_router_models.items():
    main_llm_handler.add_api(openRouterApi(
        OPEN_ROUTER_API_KEY, name=model_name, model=model_id))

local_api = ollamaLocalApi(
    name="Ollama 3 Local", model="llama3", url="http://localhost:11434/v1")

ranker = Ranker(llmapi=local_api)

systhesizer = Synthesizer(llmapi=local_api)

# if OPENAI_API_KEY:
# main_llm_handler.add_api(openaiApi(OPENAI_API_KEY))
app = App(llm_handler=main_llm_handler,
          database_manager=database_manager, ranker=ranker, local_api=local_api, synthesizer=systhesizer)
app.mainloop()
