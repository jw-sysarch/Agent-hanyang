from typing import Any

import httpx

from config import ADDRESS_SEARCH_URL, HTTP_TIMEOUT_SECONDS, KEYWORD_SEARCH_URL, get_env


def auth_headers() -> dict[str, str]:
    api_key = get_env("KAKAO_REST_API_KEY")
    return {"Authorization": f"KakaoAK {api_key}"}


async def _get_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
        try:
            response = await client.get(
                url,
                headers=auth_headers(),
                params=params,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Kakao API request failed with status {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"Kakao API connection failed: {exc}") from exc
        return response.json()


async def search_keyword(
    query: str,
    size: int = 10,
    x: float | None = None,
    y: float | None = None,
    radius: int | None = None,
    page: int | None = None,
    sort: str | None = None,
    category_group_code: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "query": query,
        "size": size,
    }
    if x is not None:
        params["x"] = x
    if y is not None:
        params["y"] = y
    if radius is not None:
        params["radius"] = radius
    if page is not None:
        params["page"] = page
    if sort is not None:
        params["sort"] = sort
    if category_group_code is not None:
        params["category_group_code"] = category_group_code

    return await _get_json(KEYWORD_SEARCH_URL, params)


async def search_address(query: str, size: int = 10) -> dict[str, Any]:
    return await _get_json(
        ADDRESS_SEARCH_URL,
        {"query": query, "size": size},
    )
