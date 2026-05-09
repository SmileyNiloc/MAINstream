import os
from dotenv import load_dotenv
from src.app import App
from src.dbmanager import DatabaseManager
from src.llmapis import llmApiHandler, geminiApi, openRouterApi
load_dotenv()

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

open_router_models = {
    "Gemini Gemma 4 31B": "google/gemma-4-31b-it:free",
    "NVIDIA nemotron": "nvidia/nemotron-3-super-120b-a12b:free",
    "Poolside Laguna M.1": "poolside/laguna-m.1:free",
    "Owl Alpha": "openrouter/owl-alpha",
    "Baidu Qianfan: CoBuddy": "baidu/cobuddy:free",
    "OpenAI: gpt-oss-120b": "openai/gpt-oss-120b:free",
    #    "Anthropic: Claude Haiku 4.5": "anthropic/claude-haiku-4.5" # This one is not free

}

for model_name, model_id in open_router_models.items():
    main_llm_handler.add_api(openRouterApi(
        OPEN_ROUTER_API_KEY, name=model_name, model=model_id))

# if OPENAI_API_KEY:
# main_llm_handler.add_api(openaiApi(OPENAI_API_KEY))
app = App(llm_handler=main_llm_handler, database_manager=database_manager)
app.mainloop()
