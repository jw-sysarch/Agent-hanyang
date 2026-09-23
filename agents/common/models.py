import os

from dotenv import load_dotenv
from google.adk.models.lite_llm import LiteLlm

load_dotenv()


def build_model():
    provider = os.getenv("MODEL_PROVIDER", "ollama").strip().lower()
    if provider == "ollama":
        ollama_api_base = os.getenv("OLLAMA_API_BASE")
        return LiteLlm(
            model=os.getenv("OLLAMA_MODEL", "ollama_chat/llama3.1:8b"),
            api_base=ollama_api_base if ollama_api_base else None,
        )
    elif provider == "openai":
        return LiteLlm(model=os.getenv("OPENAI_MODEL", "openai/gpt-4o-mini"))
    return os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
