from typing import Any

from student_place_intents import StudentPlaceIntent, detect_mood_keys


NEGATIVE_PLACE_KEYWORDS = (
    "술집",
    "주점",
    "호프",
    "포차",
    "바 ",
    "bar",
    "노래",
    "클럽",
)


def _place_text(place: dict[str, Any]) -> str:
    return " ".join(
        str(value or "").lower()
        for value in (
            place.get("name"),
            place.get("category"),
            place.get("address"),
            place.get("road_address"),
        )
    )


def _distance_m(place: dict[str, Any]) -> int | None:
    distance = place.get("distance_m")
    if distance in (None, ""):
        return None
    try:
        return int(float(distance))
    except (TypeError, ValueError):
        return None


def _add_score(score: int, reasons: list[str], points: int, reason: str) -> int:
    if reason not in reasons:
        reasons.append(reason)
    return score + points


def _distance_score(place: dict[str, Any], reasons: list[str]) -> int:
    distance = _distance_m(place)
    if distance is None:
        return 0
    if distance <= 250:
        reasons.append("도보 매우 가까움")
        return 25
    if distance <= 600:
        reasons.append("도보권")
        return 18
    if distance <= 1000:
        reasons.append("이동 부담 낮음")
        return 10
    return 0


def _intent_score(
    place: dict[str, Any],
    intent: StudentPlaceIntent,
    group_size: int,
    mood_keys: list[str],
    reasons: list[str],
) -> int:
    text = _place_text(place)
    score = 0

    if intent.key == "study":
        if "스터디카페" in text:
            score = _add_score(score, reasons, 45, "공부 목적에 적합")
        if "도서관" in text:
            score = _add_score(score, reasons, 40, "학습 공간 키워드 매칭")
        if "북카페" in text:
            score = _add_score(score, reasons, 35, "조용한 카페 계열")
        if "카페" in text or place.get("category_group_code") == "CE7":
            score = _add_score(score, reasons, 15, "카페 후보")
        if group_size >= 3 and ("스터디룸" in text or "회의실" in text):
            score = _add_score(score, reasons, 20, "여럿이 공부하기 좋음")

    elif intent.key == "team_project":
        if "스터디룸" in text:
            score = _add_score(score, reasons, 55, "팀플 목적에 적합")
        if "회의실" in text:
            score = _add_score(score, reasons, 50, "회의 공간 키워드 매칭")
        if "공유오피스" in text:
            score = _add_score(score, reasons, 35, "모임 공간 후보")
        if "카페" in text or place.get("category_group_code") == "CE7":
            score = _add_score(score, reasons, 15, "가벼운 미팅 가능")
        if group_size >= 3 and any(keyword in text for keyword in ("룸", "회의", "스터디")):
            score = _add_score(score, reasons, 20, "그룹 이용에 적합")
        if "도서관" in text and "스터디룸" not in text:
            score -= 10

    elif intent.key == "meeting":
        if "카페" in text or place.get("category_group_code") == "CE7":
            score = _add_score(score, reasons, 35, "대화하기 좋은 카페 계열")
        if "라운지" in text:
            score = _add_score(score, reasons, 25, "라운지 키워드 매칭")
        if "스터디룸" in text or "회의실" in text:
            score = _add_score(score, reasons, 20, "예약형 미팅 공간 후보")

    elif intent.key == "cafe":
        if place.get("category_group_code") == "CE7":
            score = _add_score(score, reasons, 35, "카페 카테고리 매칭")
        if any(keyword in text for keyword in ("카페", "커피", "디저트", "베이커리")):
            score = _add_score(score, reasons, 25, "카페 키워드 매칭")

    elif intent.key == "meal":
        if place.get("category_group_code") == "FD6":
            score = _add_score(score, reasons, 35, "음식점 카테고리 매칭")
        if any(keyword in text for keyword in ("식당", "음식점", "분식", "한식", "중식", "일식", "양식")):
            score = _add_score(score, reasons, 25, "식사 키워드 매칭")

    elif intent.key == "print":
        if any(keyword in text for keyword in ("프린트", "인쇄", "복사", "제본", "문구")):
            score = _add_score(score, reasons, 55, "인쇄/복사 키워드 매칭")

    if "quiet" in mood_keys and any(keyword in text for keyword in ("스터디", "도서관", "북카페", "조용")):
        score = _add_score(score, reasons, 15, "조용한 분위기 후보")
    if "spacious" in mood_keys and any(keyword in text for keyword in ("대형", "라운지", "룸", "회의실")):
        score = _add_score(score, reasons, 12, "넓은 공간 후보")
    if "late" in mood_keys and any(keyword in text for keyword in ("24시", "24시간", "무인")):
        score = _add_score(score, reasons, 12, "늦은 시간 이용 후보")

    if any(keyword in text for keyword in NEGATIVE_PLACE_KEYWORDS):
        score -= 35
        reasons.append("학생 학습/미팅 목적과 거리가 있음")

    query_hits = place.get("query_hits")
    if isinstance(query_hits, int) and query_hits > 1:
        score += min(18, 6 * (query_hits - 1))
        reasons.append("여러 검색어에서 반복 매칭")

    return score


def score_student_place(
    place: dict[str, Any],
    intent: StudentPlaceIntent,
    purpose: str,
    mood: str | None,
    group_size: int,
) -> dict[str, Any]:
    reasons: list[str] = []
    mood_keys = detect_mood_keys(purpose, mood)
    score = 30
    score += _distance_score(place, reasons)
    score += _intent_score(place, intent, group_size, mood_keys, reasons)

    ranked_place = place.copy()
    ranked_place["distance_m"] = _distance_m(place)
    ranked_place["student_fit_score"] = max(0, score)
    ranked_place["recommendation_reasons"] = reasons[:4]
    return ranked_place


def rank_student_places(
    places: list[dict[str, Any]],
    intent: StudentPlaceIntent,
    purpose: str,
    mood: str | None,
    group_size: int,
) -> list[dict[str, Any]]:
    scored_places = [
        score_student_place(
            place=place,
            intent=intent,
            purpose=purpose,
            mood=mood,
            group_size=group_size,
        )
        for place in places
    ]

    return sorted(
        scored_places,
        key=lambda place: (
            place.get("student_fit_score", 0),
            -(place.get("distance_m") or 999999),
        ),
        reverse=True,
    )
