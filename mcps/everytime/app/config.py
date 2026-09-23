import os
from dataclasses import dataclass


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    home_url: str
    cookie: str
    api_base_url: str
    host: str
    port: int
    log_level: str

def get_settings() -> Settings:
    return Settings(
        home_url=_required("EVERYTIME_HOME_URL"),
        cookie=_required("EVERYTIME_COOKIE"),
        api_base_url=os.getenv("EVERYTIME_API_BASE_URL", "https://api.everytime.kr").strip()
        or "https://api.everytime.kr",
        host=os.getenv("HOST", "0.0.0.0").strip() or "0.0.0.0",
        port=int(os.getenv("PORT", "8004")),
        log_level=os.getenv("LOG_LEVEL", "info").strip() or "info",
    )
