import os

from dotenv import load_dotenv

load_dotenv()

KAKAO_LOCAL_API_BASE = os.getenv(
    "KAKAO_LOCAL_API_BASE",
    "https://dapi.kakao.com/v2/local/search",
)
KEYWORD_SEARCH_URL = f"{KAKAO_LOCAL_API_BASE}/keyword.json"
ADDRESS_SEARCH_URL = f"{KAKAO_LOCAL_API_BASE}/address.json"
HTTP_TIMEOUT_SECONDS = 30.0


def get_env(key: str, default: str | None = None) -> str:
    value = os.getenv(key, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


def get_server_settings() -> dict[str, str | int]:
    return {
        "transport": os.getenv("FASTMCP_TRANSPORT", "streamable-http"),
        "host": os.getenv("FASTMCP_HOST", "0.0.0.0"),
        "port": int(os.getenv("FASTMCP_PORT", "8006")),
    }
