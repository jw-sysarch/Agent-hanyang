import asyncio
from typing import Any

from kakao_local_api import search_address, search_keyword
from location_utils import normalize_location_text, rank_location_candidates, select_resolved_candidate
from place_formatters import address_candidate_item, keyword_place_item, resolved_center
from student_place_intents import build_student_place_search_queries, classify_student_place_intent
from student_place_ranker import rank_student_places

VALID_SORTS = {"distance", "accuracy"}
MAX_KAKAO_SIZE = 15
MAX_KAKAO_RADIUS = 20000
NumericInt = int | str
NumericFloat = float | int | str


def _merge_keyword_candidates(*candidate_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged_candidates: dict[str, dict[str, Any]] = {}
    for candidates in candidate_groups:
        for candidate in candidates:
            candidate_key = _keyword_candidate_key(candidate)
            existing = merged_candidates.get(candidate_key)
            if existing:
                existing["query_hits"] = int(existing.get("query_hits", 1)) + 1
                continue
            merged_candidates[candidate_key] = candidate.copy()
    return list(merged_candidates.values())


def _keyword_candidate_key(candidate: dict[str, Any]) -> str:
    return str(candidate.get("id") or f"{candidate.get('name')}|{candidate.get('x')}|{candidate.get('y')}")


def _merge_student_place_candidates(
    *candidate_groups: tuple[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    merged_candidates: dict[str, dict[str, Any]] = {}
    for search_query, candidates in candidate_groups:
        for candidate in candidates:
            candidate_key = _keyword_candidate_key(candidate)
            existing = merged_candidates.get(candidate_key)
            if existing:
                existing["query_hits"] = int(existing.get("query_hits", 1)) + 1
                matched_queries = existing.setdefault("matched_queries", [])
                if search_query not in matched_queries:
                    matched_queries.append(search_query)
                continue

            item = candidate.copy()
            item["matched_queries"] = [search_query]
            merged_candidates[candidate_key] = item
    return list(merged_candidates.values())


def _coerce_int(value: NumericInt, field_name: str) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped and stripped.lstrip("-").isdigit():
            return int(stripped)
    raise ValueError(f"{field_name} must be an integer")


def _coerce_float(value: NumericFloat, field_name: str) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        try:
            return float(stripped)
        except ValueError:
            pass
    raise ValueError(f"{field_name} must be a number")

# Input validation functions
def _validate_size(size: int) -> None:
    if size < 1 or size > MAX_KAKAO_SIZE:
        raise ValueError(f"size must be between 1 and {MAX_KAKAO_SIZE}")


def _validate_page(page: int) -> None:
    if page < 1:
        raise ValueError("page must be greater than or equal to 1")


def _validate_coordinates(latitude: float, longitude: float) -> None:
    if latitude < -90 or latitude > 90:
        raise ValueError("latitude must be between -90 and 90")
    if longitude < -180 or longitude > 180:
        raise ValueError("longitude must be between -180 and 180")


def _validate_search_options(query: str, radius: int, size: int, page: int, sort: str) -> None:
    if not query.strip():
        raise ValueError("query must not be empty")
    if radius < 1 or radius > MAX_KAKAO_RADIUS:
        raise ValueError(f"radius must be between 1 and {MAX_KAKAO_RADIUS}")
    _validate_size(size)
    _validate_page(page)
    if sort not in VALID_SORTS:
        raise ValueError("sort must be either 'distance' or 'accuracy'")


def _validate_group_size(group_size: int) -> None:
    if group_size < 1:
        raise ValueError("group_size must be greater than or equal to 1")

# Service functions
async def resolve_location(location: str, size: NumericInt = 5) -> dict[str, Any]:
    size = _coerce_int(size, "size")
    if not location.strip():
        raise ValueError("location must not be empty")
    _validate_size(size)

    normalized_location = normalize_location_text(location)
    if not normalized_location:
        raise ValueError("location must contain searchable text")

    station_query = normalized_location[:-1].strip() if normalized_location.endswith("역") else normalized_location

    if normalized_location.endswith("역"):
        keyword_data = await search_keyword(
            query=station_query,
            size=size,
            sort="accuracy",
            category_group_code="SW8",
        )
        secondary_keyword_data = await search_keyword(
            query=normalized_location,
            size=size,
            sort="accuracy",
            category_group_code="SW8",
        )
        keyword_candidates = _merge_keyword_candidates(
            [
                keyword_place_item(place)
                for place in keyword_data.get("documents", [])
            ],
            [
                keyword_place_item(place)
                for place in secondary_keyword_data.get("documents", [])
            ],
        )
    else:
        keyword_data = await search_keyword(
            query=normalized_location,
            size=size,
            sort="accuracy",
        )
        keyword_candidates = [
            keyword_place_item(place)
            for place in keyword_data.get("documents", [])
        ]
    keyword_candidates = rank_location_candidates(keyword_candidates, normalized_location)
    resolved_keyword_candidate = select_resolved_candidate(keyword_candidates, normalized_location)
    if resolved_keyword_candidate:
        return {
            "query": location,
            "normalized_query": normalized_location,
            "search_query": station_query if normalized_location.endswith("역") else normalized_location,
            "match_type": "keyword",
            "resolved": resolved_keyword_candidate,
            "candidates": keyword_candidates,
            "count": len(keyword_candidates),
        }

    address_data = await search_address(query=normalized_location, size=size)
    address_candidates = [
        address_candidate_item(place)
        for place in address_data.get("documents", [])
    ]
    address_candidates = rank_location_candidates(address_candidates, normalized_location)
    resolved_address_candidate = select_resolved_candidate(address_candidates, normalized_location)
    return {
        "query": location,
        "normalized_query": normalized_location,
        "search_query": normalized_location,
        "match_type": "address" if resolved_address_candidate else "none",
        "resolved": resolved_address_candidate,
        "candidates": address_candidates,
        "count": len(address_candidates),
    }


async def search_nearby_places(
    latitude: NumericFloat,
    longitude: NumericFloat,
    query: str = "카페",
    radius: NumericInt = 1000,
    size: NumericInt = 10,
    page: NumericInt = 1,
    sort: str = "distance",
) -> dict[str, Any]:
    latitude = _coerce_float(latitude, "latitude")
    longitude = _coerce_float(longitude, "longitude")
    radius = _coerce_int(radius, "radius")
    size = _coerce_int(size, "size")
    page = _coerce_int(page, "page")
    _validate_coordinates(latitude, longitude)
    _validate_search_options(query=query, radius=radius, size=size, page=page, sort=sort)

    data = await search_keyword(
        query=query,
        x=longitude,
        y=latitude,
        radius=radius,
        size=size,
        page=page,
        sort=sort,
    )

    places = [keyword_place_item(place) for place in data.get("documents", [])]
    meta = data.get("meta", {})
    return {
        "query": query,
        "center": {
            "latitude": latitude,
            "longitude": longitude,
        },
        "radius": radius,
        "page": page,
        "size": size,
        "is_end": meta.get("is_end", True),
        "pageable_count": meta.get("pageable_count", 0),
        "total_count": meta.get("total_count", 0),
        "places": places,
    }


async def search_places_near_location(
    location: str,
    query: str = "카페",
    radius: NumericInt = 1000,
    size: NumericInt = 10,
    page: NumericInt = 1,
    sort: str = "distance",
) -> dict[str, Any]:
    radius = _coerce_int(radius, "radius")
    size = _coerce_int(size, "size")
    page = _coerce_int(page, "page")

    location_result = await resolve_location(location=location, size=5)
    center = resolved_center(location_result)
    if not center:
        return {
            "location": location,
            "query": query,
            "resolved_location": None,
            "places": [],
            "count": 0,
            "message": "No matching location could be resolved.",
        }

    nearby_result = await search_nearby_places(
        latitude=float(center["latitude"]),
        longitude=float(center["longitude"]),
        query=query,
        radius=radius,
        size=size,
        page=page,
        sort=sort,
    )
    nearby_result["location"] = location
    nearby_result["resolved_location"] = center
    return nearby_result


async def find_student_places(
    location: str,
    purpose: str = "공부",
    group_size: NumericInt = 1,
    mood: str | None = None,
    radius: NumericInt = 800,
    size: NumericInt = 10,
    sort: str = "distance",
) -> dict[str, Any]:
    radius = _coerce_int(radius, "radius")
    size = _coerce_int(size, "size")
    group_size = _coerce_int(group_size, "group_size")
    _validate_search_options(query=purpose, radius=radius, size=size, page=1, sort=sort)
    _validate_group_size(group_size)

    location_result = await resolve_location(location=location, size=5)
    center = resolved_center(location_result)
    if not center:
        return {
            "location": location,
            "purpose": purpose,
            "mood": mood,
            "resolved_location": None,
            "places": [],
            "count": 0,
            "message": "No matching location could be resolved.",
        }

    intent = classify_student_place_intent(purpose=purpose, mood=mood)
    search_queries = build_student_place_search_queries(
        intent=intent,
        purpose=purpose,
        mood=mood,
    )
    per_query_size = min(MAX_KAKAO_SIZE, max(size, 8))

    search_results = await asyncio.gather(
        *[
            search_keyword(
                query=search_query.query,
                x=float(center["longitude"]),
                y=float(center["latitude"]),
                radius=radius,
                size=per_query_size,
                sort=sort,
                category_group_code=search_query.category_group_code,
            )
            for search_query in search_queries
        ]
    )

    candidate_groups = [
        (
            search_query.query,
            [
                keyword_place_item(place)
                for place in search_result.get("documents", [])
            ],
        )
        for search_query, search_result in zip(search_queries, search_results)
    ]
    merged_candidates = _merge_student_place_candidates(*candidate_groups)
    ranked_places = rank_student_places(
        places=merged_candidates,
        intent=intent,
        purpose=purpose,
        mood=mood,
        group_size=group_size,
    )

    return {
        "location": location,
        "purpose": purpose,
        "normalized_purpose": intent.key,
        "purpose_label": intent.label,
        "mood": mood,
        "group_size": group_size,
        "resolved_location": center,
        "radius": radius,
        "size": size,
        "sort": sort,
        "search_queries": [
            {
                "query": search_query.query,
                "category_group_code": search_query.category_group_code,
            }
            for search_query in search_queries
        ],
        "places": ranked_places[:size],
        "count": min(len(ranked_places), size),
        "candidates_considered": len(merged_candidates),
    }
