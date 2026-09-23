from dataclasses import dataclass


@dataclass(frozen=True)
class StudentPlaceIntent:
    key: str
    label: str
    aliases: tuple[str, ...]
    search_queries: tuple[str, ...]
    category_group_code: str | None = None


@dataclass(frozen=True)
class StudentPlaceSearchQuery:
    query: str
    category_group_code: str | None = None


STUDENT_PLACE_INTENTS = {
    "team_project": StudentPlaceIntent(
        key="team_project",
        label="팀플/회의",
        aliases=(
            "팀플",
            "조별",
            "조모임",
            "팀프로젝트",
            "팀 프로젝트",
            "팀미팅",
            "프로젝트미팅",
            "회의",
            "토론",
            "발표 준비",
            "스터디룸",
            "회의실",
            "모임",
        ),
        search_queries=("스터디룸", "회의실", "공유오피스", "카페"),
    ),
    "study": StudentPlaceIntent(
        key="study",
        label="공부",
        aliases=(
            "공부",
            "스터디",
            "과제",
            "자습",
            "노트북",
            "코딩",
            "공강",
            "집중",
            "열람",
            "도서관",
            "독서",
        ),
        search_queries=("스터디카페", "도서관", "북카페", "카페"),
    ),
    "meeting": StudentPlaceIntent(
        key="meeting",
        label="미팅/대화",
        aliases=("미팅", "만남", "약속", "상담", "면담", "대화", "커피챗"),
        search_queries=("카페", "스터디룸", "회의실", "라운지"),
    ),
    "cafe": StudentPlaceIntent(
        key="cafe",
        label="카페",
        aliases=("카페", "커피", "디저트", "음료", "차"),
        search_queries=("카페", "커피", "디저트 카페"),
        category_group_code="CE7",
    ),
    "meal": StudentPlaceIntent(
        key="meal",
        label="식사",
        aliases=("밥", "식사", "점심", "저녁", "맛집", "식당", "음식점"),
        search_queries=("식당", "음식점", "맛집", "분식"),
        category_group_code="FD6",
    ),
    "print": StudentPlaceIntent(
        key="print",
        label="인쇄/복사",
        aliases=("프린트", "인쇄", "복사", "제본", "문구", "출력"),
        search_queries=("프린트", "복사", "인쇄", "문구"),
    ),
}


MOOD_QUERY_HINTS = {
    "quiet": {
        "aliases": ("조용", "차분", "집중", "조용한"),
        "queries": ("조용한 카페", "스터디카페", "북카페"),
    },
    "late": {
        "aliases": ("늦게", "밤", "야간", "24시", "24시간"),
        "queries": ("24시 카페", "무인 스터디카페"),
    },
    "spacious": {
        "aliases": ("넓", "자리", "여유", "쾌적"),
        "queries": ("대형 카페", "스터디룸"),
    },
}


def _normalize_text(text: str | None) -> str:
    return (text or "").strip().lower().replace(" ", "")


def classify_student_place_intent(purpose: str, mood: str | None = None) -> StudentPlaceIntent:
    normalized = _normalize_text(f"{purpose} {mood or ''}")
    if not normalized:
        return STUDENT_PLACE_INTENTS["study"]

    scored_intents: list[tuple[int, StudentPlaceIntent]] = []
    for intent in STUDENT_PLACE_INTENTS.values():
        score = sum(1 for alias in intent.aliases if _normalize_text(alias) in normalized)
        if score > 0:
            scored_intents.append((score, intent))

    if not scored_intents:
        return STUDENT_PLACE_INTENTS["study"]

    return sorted(scored_intents, key=lambda item: item[0], reverse=True)[0][1]


def detect_mood_keys(purpose: str, mood: str | None = None) -> list[str]:
    normalized = _normalize_text(f"{purpose} {mood or ''}")
    mood_keys = []
    for mood_key, config in MOOD_QUERY_HINTS.items():
        if any(_normalize_text(alias) in normalized for alias in config["aliases"]):
            mood_keys.append(mood_key)
    return mood_keys


def build_student_place_search_queries(
    intent: StudentPlaceIntent,
    purpose: str,
    mood: str | None = None,
    max_queries: int = 4,
) -> list[StudentPlaceSearchQuery]:
    queries: list[StudentPlaceSearchQuery] = []
    seen_queries: set[str] = set()

    for mood_key in detect_mood_keys(purpose, mood):
        for query in MOOD_QUERY_HINTS[mood_key]["queries"]:
            normalized_query = _normalize_text(query)
            if normalized_query not in seen_queries:
                queries.append(StudentPlaceSearchQuery(query=query))
                seen_queries.add(normalized_query)

    for query in intent.search_queries:
        normalized_query = _normalize_text(query)
        if normalized_query in seen_queries:
            continue
        queries.append(
            StudentPlaceSearchQuery(
                query=query,
                category_group_code=intent.category_group_code,
            )
        )
        seen_queries.add(normalized_query)

    return queries[:max_queries]
