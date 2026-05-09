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
main_llm_handler.add_api(openRouterApi(
    OPEN_ROUTER_API_KEY, name="OpenRouter API"))
main_llm_handler.add_api(openRouterApi(
    OPEN_ROUTER_API_KEY, name="NVIDIA nemotron", model="nvidia/nemotron-3-super-120b-a12b:free"))
# if OPENAI_API_KEY:
# main_llm_handler.add_api(openaiApi(OPENAI_API_KEY))
app = App(llm_handler=main_llm_handler, database_manager=database_manager)
app.mainloop()
