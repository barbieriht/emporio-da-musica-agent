import os

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

DEFAULT_PROVIDER = "google_genai"
DEFAULT_MODEL = "gemini-3.7-flash"


def build_model():
    """Build the chat model from env vars (LLM_PROVIDER, LLM_MODEL, provider API key)."""
    load_dotenv()
    return init_chat_model(
        os.getenv("LLM_MODEL", DEFAULT_MODEL),
        model_provider=os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER),
        temperature=0.3,
    )


def today():
    """Today's date in the store's timezone. AGENT_TODAY=YYYY-MM-DD overrides it (demos/tests)."""
    from datetime import date, datetime

    from emporio_agent.policies import STORE_TZ

    load_dotenv()
    override = os.getenv("AGENT_TODAY")
    return date.fromisoformat(override) if override else datetime.now(STORE_TZ).date()
