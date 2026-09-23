from __future__ import annotations

import contextlib

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from app.api_app import create_api_app
from app.dependencies import get_service
from app.errors import EverytimeRequestError

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "everytime-mcp",
    "everytime-mcp:8004",
    "host.docker.internal",
    "host.docker.internal:8004",
]
INTERNAL_MCP_HOST = "localhost:8004"

mcp = FastMCP(
    "everytime-mcp",
    instructions=(
        "Read Everytime board, lecture, and timetable data. "
        "Use board IDs returned by list_boards when calling get_board_posts. "
        "Use lecture IDs returned by search_lectures or get_my_lectures when calling "
        "get_lecture_reviews."
    ),
    stateless_http=True,
    json_response=True,
)
mcp.settings.host = "0.0.0.0"
mcp.settings.streamable_http_path = "/mcp"


@mcp.tool()
def health_check() -> dict:
    """Check whether the Everytime MCP backend is alive."""
    return {"status": "ok"}


@mcp.tool()
def get_home_summary(include_cookies: bool = False) -> dict:
    """Get a summary of the Everytime home page."""
    try:
        return get_service().get_home_summary(include_cookies=include_cookies)
    except ValueError as exc:
        return {"error": str(exc)}
    except EverytimeRequestError as exc:
        return {"error": str(exc)}


@mcp.tool()
def list_boards() -> dict:
    """List available Everytime boards with board IDs."""
    try:
        return get_service().list_boards()
    except ValueError as exc:
        return {"error": str(exc)}
    except EverytimeRequestError as exc:
        return {"error": str(exc)}


@mcp.tool()
def get_board_posts(board_id: str, limit: int = 20) -> dict:
    """Get recent posts for an Everytime board by board ID."""
    try:
        return get_service().get_board_posts(board_id=board_id, limit=limit)
    except ValueError as exc:
        return {"error": str(exc)}
    except EverytimeRequestError as exc:
        return {"error": str(exc)}


@mcp.tool()
def debug_board(board_id: str) -> dict:
    """Return debug information for a board page and its XML API response."""
    try:
        return get_service().debug_board(board_id=board_id)
    except ValueError as exc:
        return {"error": str(exc)}
    except EverytimeRequestError as exc:
        return {"error": str(exc)}


@mcp.tool()
def get_my_lectures() -> dict:
    """Get lectures from the authenticated user's Everytime lecture room."""
    try:
        return get_service().get_my_lectures()
    except ValueError as exc:
        return {"error": str(exc)}
    except EverytimeRequestError as exc:
        return {"error": str(exc)}


@mcp.tool()
def get_lecture_points() -> dict:
    """Get the authenticated user's Everytime lecture review ticket/point count."""
    try:
        return get_service().get_lecture_points()
    except ValueError as exc:
        return {"error": str(exc)}
    except EverytimeRequestError as exc:
        return {"error": str(exc)}


@mcp.tool()
def search_lectures(
    keyword: str,
    year: str | None = None,
    semester: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """Search Everytime timetable subjects and lecture IDs by keyword."""
    try:
        return get_service().search_lectures(
            keyword=keyword,
            year=year,
            semester=semester,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        return {"error": str(exc)}
    except EverytimeRequestError as exc:
        return {"error": str(exc)}


@mcp.tool()
def get_recent_lecture_reviews(limit: int = 20, offset: int = 0) -> dict:
    """Get recent lecture reviews visible in Everytime lecture room."""
    try:
        return get_service().get_recent_lecture_reviews(limit=limit, offset=offset)
    except ValueError as exc:
        return {"error": str(exc)}
    except EverytimeRequestError as exc:
        return {"error": str(exc)}


@mcp.tool()
def get_lecture_reviews(
    lecture_id: str, limit: int = 20, offset: int = 0, use_cookie: bool = False
) -> dict:
    """Get reviews and ratings for one lecture by lecture ID."""
    try:
        return get_service().get_lecture_reviews(
            lecture_id=lecture_id,
            limit=limit,
            offset=offset,
            use_cookie=use_cookie,
        )
    except ValueError as exc:
        return {"error": str(exc)}
    except EverytimeRequestError as exc:
        return {"error": str(exc)}


@mcp.tool()
def get_public_lecture_page(lecture_id: str) -> dict:
    """Get public metadata for an Everytime lecture page without sending cookies."""
    try:
        return get_service().get_public_lecture_page(lecture_id=lecture_id)
    except ValueError as exc:
        return {"error": str(exc)}
    except EverytimeRequestError as exc:
        return {"error": str(exc)}


@mcp.tool()
def list_timetable_semesters() -> dict:
    """List Everytime timetable semesters available to the authenticated user."""
    try:
        return get_service().list_timetable_semesters()
    except ValueError as exc:
        return {"error": str(exc)}
    except EverytimeRequestError as exc:
        return {"error": str(exc)}


@mcp.tool()
def list_timetable_tables(year: str, semester: str) -> dict:
    """List timetable tables for a given year and semester."""
    try:
        return get_service().list_timetable_tables(year=year, semester=semester)
    except ValueError as exc:
        return {"error": str(exc)}
    except EverytimeRequestError as exc:
        return {"error": str(exc)}


@mcp.tool()
def get_timetable(table_id: str) -> dict:
    """Get subjects and meeting times for an Everytime timetable table."""
    try:
        return get_service().get_timetable(table_id=table_id)
    except ValueError as exc:
        return {"error": str(exc)}
    except EverytimeRequestError as exc:
        return {"error": str(exc)}


@mcp.tool()
def get_current_timetable() -> dict:
    """Get the primary timetable for the current formal semester."""
    try:
        return get_service().get_current_timetable()
    except ValueError as exc:
        return {"error": str(exc)}
    except EverytimeRequestError as exc:
        return {"error": str(exc)}


@contextlib.asynccontextmanager
async def lifespan(app: Starlette):
    async with mcp.session_manager.run():
        yield


async def healthz(request) -> JSONResponse:
    return JSONResponse({"status": "ok", "transport": "streamable-http", "path": "/mcp"})


class HostRewriteMiddleware:
    def __init__(self, app, rewritten_host: str):
        self.app = app
        self.rewritten_host = rewritten_host.encode("latin-1")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = []
        for key, value in scope.get("headers", []):
            if key.lower() == b"host":
                headers.append((b"host", self.rewritten_host))
            else:
                headers.append((key, value))

        rewritten_scope = dict(scope)
        rewritten_scope["headers"] = headers
        rewritten_scope["server"] = ("localhost", 8004)
        await self.app(rewritten_scope, receive, send)


mcp_http_app = HostRewriteMiddleware(
    TrustedHostMiddleware(
        mcp.streamable_http_app(),
        allowed_hosts=ALLOWED_HOSTS,
    ),
    rewritten_host=INTERNAL_MCP_HOST,
)


class EverytimeASGIApp:
    def __init__(self, mcp_app, api_app):
        self.mcp_app = mcp_app
        self.api_app = api_app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path", "").startswith("/mcp"):
            await self.mcp_app(scope, receive, send)
            return
        await self.api_app(scope, receive, send)


app = Starlette(
    routes=[
        Route("/healthz", endpoint=healthz, methods=["GET"]),
        Mount("/", app=EverytimeASGIApp(mcp_http_app, create_api_app())),
    ],
    lifespan=lifespan,
)
