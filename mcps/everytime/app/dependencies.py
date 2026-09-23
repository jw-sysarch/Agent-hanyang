from app.config import get_settings
from app.service import EverytimeService


def get_service() -> EverytimeService:
    return EverytimeService(get_settings())
