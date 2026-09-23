import os

from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app


def _parse_allow_origins(value: str | None) -> list[str] | None:
    if not value:
        return None
    origins = [origin.strip() for origin in value.split(",") if origin.strip()]
    return origins or None


def create_app() -> FastAPI:
    app = get_fast_api_app(
        agents_dir=os.getenv("AGENTS_DIR", "agents"),
        session_service_uri=os.getenv("SESSION_DB_URI"),
        artifact_service_uri=os.getenv("ARTIFACT_SERVICE_URI"),
        memory_service_uri=os.getenv("MEMORY_SERVICE_URI"),
        eval_storage_uri=os.getenv("EVAL_STORAGE_URI"),
        allow_origins=_parse_allow_origins(os.getenv("ALLOW_ORIGINS")),
        web=os.getenv("ADK_WEB_UI", "false").lower() == "true",
        a2a=os.getenv("ADK_A2A", "false").lower() == "true",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        trace_to_cloud=os.getenv("TRACE_TO_CLOUD", "false").lower() == "true",
        reload_agents=os.getenv("RELOAD_AGENTS", "false").lower() == "true",
    )

    @app.get("/", tags=["meta"])
    async def root() -> dict[str, str]:
        return {
            "name": "google-adk-agent",
            "status": "ok",
            "docs": "/docs",
            "apps": "/list-apps",
        }

    @app.get("/healthz", tags=["meta"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
