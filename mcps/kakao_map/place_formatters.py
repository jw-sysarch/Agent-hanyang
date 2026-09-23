from typing import Any


def place_display_summary(place: dict[str, Any]) -> str:
    name = place.get("name") or "이름 없음"
    distance = place.get("distance_m")
    road_address = place.get("road_address")
    address = road_address or place.get("address") or "주소 없음"
    summary_parts = [name]
    if distance:
        summary_parts.append(f"{distance}m")
    summary_parts.append(address)
    return " | ".join(summary_parts)


def keyword_place_item(place: dict[str, Any]) -> dict[str, Any]:
    item = {
        "id": place.get("id"),
        "name": place.get("place_name"),
        "category": place.get("category_name"),
        "category_group_code": place.get("category_group_code"),
        "address": place.get("address_name"),
        "road_address": place.get("road_address_name"),
        "phone": place.get("phone"),
        "distance_m": place.get("distance"),
        "x": place.get("x"),
        "y": place.get("y"),
        "place_url": place.get("place_url"),
        "query_hits": 1,
    }
    item["display_summary"] = place_display_summary(item)
    return item


def address_candidate_item(place: dict[str, Any]) -> dict[str, Any]:
    road_address = place.get("road_address") or {}
    address = place.get("address") or {}
    item = {
        "name": road_address.get("building_name") or address.get("address_name") or place.get("address_name"),
        "category": "address",
        "address": address.get("address_name") or place.get("address_name"),
        "road_address": road_address.get("address_name"),
        "x": place.get("x"),
        "y": place.get("y"),
    }
    item["display_summary"] = place_display_summary(item)
    return item


def resolved_center(location_result: dict[str, Any]) -> dict[str, Any] | None:
    resolved = location_result.get("resolved")
    if not resolved:
        return None
    return {
        "name": resolved.get("name"),
        "address": resolved.get("address"),
        "road_address": resolved.get("road_address"),
        "latitude": resolved.get("y"),
        "longitude": resolved.get("x"),
        "display_summary": resolved.get("display_summary"),
    }
