import os
from typing import Any

from dotenv import load_dotenv
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from config import get_server_settings
from services import (
    find_student_places as find_student_places_service,
    resolve_location as resolve_location_service,
    search_nearby_places as search_nearby_places_service,
    search_places_near_location as search_places_near_location_service,
)

load_dotenv()

MCP_NAME = os.getenv("MCP_NAME", "kakao-map")
PORT = int(os.getenv("PORT", "8006"))

mcp = FastMCP(MCP_NAME)


@mcp.custom_route("/healthz", methods=["GET"], include_in_schema=False)
async def healthz(_: Request) -> JSONResponse:
    return JSONResponse({"name": MCP_NAME, "status": "ok"})


@mcp.tool
async def resolve_location(location: str, size: int | str = 5) -> dict[str, Any]:
    """
    Resolve a place name or address into coordinates.

    Args:
        location: A place name, building name, station name, or address.
        size: Number of candidates to return.
    """
    return await resolve_location_service(location=location, size=size)


@mcp.tool
async def search_nearby_places(
    latitude: float | int | str,
    longitude: float | int | str,
    query: str = "카페",
    radius: int | str = 1000,
    size: int | str = 10,
    page: int | str = 1,
    sort: str = "distance",
) -> dict[str, Any]:
    """
    Search nearby places around a given latitude/longitude using Kakao Local keyword search.

    Args:
        latitude: Center latitude.
        longitude: Center longitude.
        query: Search keyword, for example `카페`, `편의점`, `약국`.
        radius: Search radius in meters. Kakao Local allows up to 20000.
        size: Number of items to return. Kakao Local allows up to 15.
        page: Page number starting from 1.
        sort: `distance` or `accuracy`.
    """
    return await search_nearby_places_service(
        latitude=latitude, longitude=longitude, query=query,
        radius=radius, size=size, page=page, sort=sort,
    )


@mcp.tool
async def search_places_near_location(
    location: str,
    query: str = "카페",
    radius: int | str = 1000,
    size: int | str = 10,
    page: int | str = 1,
    sort: str = "distance",
) -> dict[str, Any]:
    """
    Resolve a place name or address first, then search nearby places around it.

    Args:
        location: A place name, building name, station name, campus name, or address.
        query: Search keyword, for example `카페`, `편의점`, `약국`.
        radius: Search radius in meters. Kakao Local allows up to 20000.
        size: Number of items to return. Kakao Local allows up to 15.
        page: Page number starting from 1.
        sort: `distance` or `accuracy`.
    """
    return await search_places_near_location_service(
        location=location, query=query, radius=radius,
        size=size, page=page, sort=sort,
    )


@mcp.tool
async def find_student_places(
    location: str,
    purpose: str = "공부",
    group_size: int | str = 1,
    mood: str | None = None,
    radius: int | str = 800,
    size: int | str = 10,
    sort: str = "distance",
) -> dict[str, Any]:
    """
    Find student-friendly places around a school location for studying, team projects, meetings, cafes, meals, or printing.

    Args:
        location: School, campus area, building name, station, or address to search around.
        purpose: Student intent such as `공부`, `팀플`, `미팅`, `카페`, `밥`, or `프린트`.
        group_size: Number of people expected to use the place.
        mood: Optional preference such as `조용한`, `넓은`, or `늦게까지`.
        radius: Search radius in meters. Kakao Local allows up to 20000.
        size: Number of ranked places to return. Kakao Local allows up to 15.
        sort: `distance` or `accuracy` for each Kakao search query.
    """
    return await find_student_places_service(
        location=location, purpose=purpose, group_size=group_size,
        mood=mood, radius=radius, size=size, sort=sort,
    )


if __name__ == "__main__":
    settings = get_server_settings()
    mcp.run(
        transport=settings["transport"],
        host=settings["host"],
        port=settings["port"],
    )
