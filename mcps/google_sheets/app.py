import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

MCP_NAME = os.getenv("MCP_NAME", "google_sheets")
PORT = int(os.getenv("PORT", "8003"))

app = FastAPI(title=f"{MCP_NAME} MCP")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"name": MCP_NAME, "status": "ok"}


@app.get("/manifest")
async def manifest() -> dict[str, object]:
    return {
        "name": MCP_NAME,
        "kind": "mcp-placeholder",
        "tools": [],
        "message": "Replace this placeholder with the migrated Google Sheets MCP server.",
    }


if __name__ == "__main__":
    uvicorn.run("app:app", host=os.getenv("HOST", "0.0.0.0"), port=PORT)
