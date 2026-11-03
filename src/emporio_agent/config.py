import os

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

DEFAULT_PROVIDER = "google_genai"
DEFAULT_MODEL = "gemini-3.8-flash"


def build_model():
    """Build the chat model from env vars (LLM_PROVIDER, LLM_MODEL, provider API key)."""
    load_dotenv()
    return init_chat_model(
        os.getenv("LLM_MODEL", DEFAULT_MODEL),
        model_provider=os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER),
        temperature=0.3,
    )
