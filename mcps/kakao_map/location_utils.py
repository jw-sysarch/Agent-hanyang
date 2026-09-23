import re
from typing import Any

LOCATION_SUFFIXES = [
    " 주변의",
    " 주변에서",
    " 주변",
    " 근처의",
    " 근처에서",
    " 근처",
    " 인근의",
    " 인근에서",
    " 인근",
    " 부근의",
    " 부근에서",
    " 부근",
    " 근방의",
    " 근방에서",
    " 근방",
    " 쪽에서",
    " 쪽",
]

LOCATION_ANCHOR_PATTERNS = [
    re.compile(r"([가-힣A-Za-z0-9]+역)"),
    re.compile(r"([가-힣A-Za-z0-9]+대학교(?:병원)?(?:\s*[가-힣A-Za-z0-9]+캠퍼스)?)"),
    re.compile(r"([가-힣A-Za-z0-9]+대)"),
    re.compile(r"([가-힣A-Za-z0-9]+캠퍼스)"),
]

PLACE_SEARCH_HINTS = [
    "카페",
    "맛집",
    "식당",
    "음식점",
    "편의점",
    "약국",
    "병원",
    "은행",
    "주차장",
    "마트",
    "추천",
    "찾아",
    "알려",
]
TRANSIT_CATEGORY_KEYWORDS = ("지하철", "전철", "역")


def _strip_after_location_suffix(location: str) -> str:
    for suffix in LOCATION_SUFFIXES:
        if suffix in location:
            return location.split(suffix, 1)[0].strip()
    return location


def _extract_anchor_from_sentence(location: str) -> str:
    if not any(hint in location for hint in PLACE_SEARCH_HINTS):
        return location

    for pattern in LOCATION_ANCHOR_PATTERNS:
        match = pattern.search(location)
        if match:
            return match.group(1).strip()
    return location


def normalize_location_text(location: str) -> str:
    normalized = location.strip()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = _strip_after_location_suffix(normalized)
    normalized = _extract_anchor_from_sentence(normalized)
    for suffix in LOCATION_SUFFIXES:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)].strip()
    return normalized


# 카카오 API가 반환하는 노선 접미사 패턴 (예: "한양대역 2호선", "왕십리역 분당선")
_LINE_SUFFIX_RE = re.compile(
    r"\s+(?:\d+호선|경의중앙선|분당선|신분당선|경춘선|경강선|서해선|수인선|인천[12]호선"
    r"|공항철도|우이신설선|신림선|GTX-[A-Z]|김포골드라인|에버라인|용인경전철"
    r"|의정부경전철|자기부상|[가-힣]+선)$"
)


def _strip_line_suffix(text: str) -> str:
    """Remove trailing subway/rail line name from station text."""
    return _LINE_SUFFIX_RE.sub("", text).strip()


def _normalize_station_name(text: str) -> str:
    normalized = text.strip().lower()
    normalized = _strip_line_suffix(normalized)
    if normalized.endswith("역"):
        return normalized[:-1].strip()
    return normalized


def is_station_query(location: str) -> bool:
    return location.strip().endswith("역")


def is_transit_candidate(candidate: dict[str, Any]) -> bool:
    name = (candidate.get("name") or "").strip().lower()
    category = (candidate.get("category") or "").strip().lower()
    category_group_code = (candidate.get("category_group_code") or "").strip().upper()
    return (
        category_group_code == "SW8"
        or name.endswith("역")
        or any(keyword in category for keyword in TRANSIT_CATEGORY_KEYWORDS)
    )


def is_exact_location_name_match(candidate: dict[str, Any], location: str) -> bool:
    name = (candidate.get("name") or "").strip().lower()
    target = location.strip().lower()
    if name == target:
        return True
    if is_station_query(location):
        # "한양대역 2호선" vs "한양대역" → 노선 접미사를 떼고 비교
        stripped_name = _strip_line_suffix(name)
        if stripped_name == target:
            return True
        return _normalize_station_name(name) == _normalize_station_name(target)
    return False


def location_match_score(candidate: dict[str, Any], location: str) -> int:
    if not location:
        return 0
    name = (candidate.get("name") or "").strip().lower()
    address = (candidate.get("address") or "").strip().lower()
    road_address = (candidate.get("road_address") or "").strip().lower()
    category = (candidate.get("category") or "").strip().lower()
    target = location.strip().lower()
    normalized_name = _normalize_station_name(name)
    normalized_target = _normalize_station_name(target)

    score = 0
    if name == target:
        score += 120
    elif target and target in name:
        score += 80

    if normalized_name and normalized_name == normalized_target:
        score += 110
    elif normalized_target and normalized_target in normalized_name:
        score += 70

    if is_exact_location_name_match(candidate, location):
        score += 80

    if road_address == target or address == target:
        score += 70
    elif target and (target in road_address or target in address):
        score += 40

    if is_station_query(location) and is_transit_candidate(candidate):
        score += 60
        if normalized_name == normalized_target:
            score += 120

    query_hits = candidate.get("query_hits")
    if isinstance(query_hits, int) and query_hits > 1:
        score += 50 * (query_hits - 1)
    return score


def rank_location_candidates(candidates: list[dict[str, Any]], location: str) -> list[dict[str, Any]]:
    return sorted(
        candidates,
        key=lambda candidate: location_match_score(candidate, location),
        reverse=True,
    )


def select_resolved_candidate(candidates: list[dict[str, Any]], location: str) -> dict[str, Any] | None:
    if not candidates:
        return None

    ranked_candidates = rank_location_candidates(candidates, location)
    top_candidate = ranked_candidates[0]
    top_score = location_match_score(top_candidate, location)
    second_score = location_match_score(ranked_candidates[1], location) if len(ranked_candidates) > 1 else None

    if is_station_query(location):
        exact_transit_candidates = [
            candidate
            for candidate in ranked_candidates
            if is_transit_candidate(candidate) and is_exact_location_name_match(candidate, location)
        ]
        if len(exact_transit_candidates) == 0:
            return None
        # 같은 역의 여러 노선 결과가 있을 수 있으므로 최고점을 선택
        best = exact_transit_candidates[0]
        # 2위 후보가 완전히 다른 역 이름이면서 점수가 비슷한 경우에만 애매함 → 그래도 1위가 exact match이므로 반환
        return best

    if is_exact_location_name_match(top_candidate, location):
        if second_score is not None and second_score >= top_score - 10:
            return None
        return top_candidate

    if top_score >= 180 and (second_score is None or second_score <= top_score - 40):
        return top_candidate
    return None
