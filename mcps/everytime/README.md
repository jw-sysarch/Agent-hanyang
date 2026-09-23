# everytimeMCP

에브리타임 로그인 세션 쿠키를 사용해 데이터를 읽는 프로젝트입니다.
지금 구조는 하나의 Everytime 서비스 포트에서 HTTP API와 MCP를 함께 제공합니다.

- HTTP API: `/api/...`
- FastMCP: `/mcp`

공용 로직은 한 곳에서 관리하고, HTTP와 MCP가 같은 서비스 레이어를 재사용합니다.

## 현재 지원 범위

- 홈 페이지 요약 조회
- 게시판 목록 조회
- 특정 게시판 글 목록 조회
- 게시판 디버그 조회
- 개인 강의실 수강내역 조회
- 강의평 티켓/포인트 조회
- 최근 강의평 조회
- 강의/과목 검색
- 강의별 공개 페이지 메타데이터 및 강의평 조회
- 시간표 학기/시간표 목록/시간표 상세 조회
- 현재 학기 대표 시간표 조회
- FastMCP tool 제공

현재 미지원:

- 글 본문 단건 조회
- 댓글 조회
- 로그인 자동화
- 쿠키 자동 갱신

## 프로젝트 구조

```text
app/
  api_app.py         FastAPI 앱 팩토리
  mcp_app.py         FastMCP + Starlette 앱
  service.py         공용 서비스 레이어
  scraper.py         에브리타임 요청/파싱 로직
  models.py          응답 모델
  errors.py          공용 예외
  dependencies.py    서비스 생성
  config.py          환경 변수 로드
  app.py             HTTP API 단독 엔트리포인트
```

## 데이터 수집 방식

- 홈 페이지: `https://everytime.kr/` HTML 조회
- 게시판 목록: 홈 HTML에서 추출
- 게시판 글 목록: 에브리타임 웹 프론트가 사용하는 XML API 호출
  - `POST /find/board/article/list`

즉 게시판 글 목록은 HTML 파싱이 아니라 실제 웹앱 요청을 그대로 사용합니다.

## 환경 변수

`.env.example`를 복사해 `.env`를 만든 뒤 값을 채웁니다.

```env
EVERYTIME_HOME_URL=https://everytime.kr/
EVERYTIME_COOKIE=
EVERYTIME_API_BASE_URL=https://api.everytime.kr

HOST=0.0.0.0
PORT=8004
LOG_LEVEL=info
```

설명:

- `EVERYTIME_COOKIE`: 브라우저에서 로그인한 세션의 `Cookie` 헤더 전체 문자열
- `EVERYTIME_API_BASE_URL`: 게시판 글 목록 XML API 서버

## 쿠키 가져오는 법

1. 브라우저에서 `https://everytime.kr/` 로그인 상태를 만듭니다.
2. 개발자도구를 엽니다.
3. `Network` 탭에서 `everytime.kr` 요청 하나를 클릭합니다.
4. `Request Headers`의 `Cookie` 값을 전체 복사합니다.
5. `.env`의 `EVERYTIME_COOKIE=` 뒤에 그대로 붙여넣습니다.

예시:

```env
EVERYTIME_COOKIE=SESSION=...; other_cookie=...
```

## 실행

Everytime 서비스를 띄웁니다.

```bash
docker compose build --no-cache
docker compose up
```

기본 포트:

- HTTP API: `http://localhost:8004`
- MCP health: `http://localhost:8004/healthz`
- MCP endpoint: `http://localhost:8004/mcp`

## HTTP API

### Health Check

```bash
curl http://localhost:8004/health
```

### 홈 페이지 요약

```bash
curl http://localhost:8004/api/home
curl "http://localhost:8004/api/home?include_cookies=true"
```

응답 예시:

```json
{
  "url": "https://everytime.kr/",
  "title": "에브리타임",
  "headings": ["한양대 서울캠 에브리타임"],
  "links": [
    {
      "text": "자유게시판",
      "href": "https://everytime.kr/370440"
    }
  ],
  "text_preview": "..."
}
```

### 게시판 목록

```bash
curl http://localhost:8004/api/boards
```

응답 예시:

```json
{
  "boards": [
    {
      "id": "370440",
      "name": "자유게시판",
      "href": "https://everytime.kr/370440"
    },
    {
      "id": "255679",
      "name": "비밀게시판",
      "href": "https://everytime.kr/255679"
    }
  ]
}
```

### 게시판 글 목록

`zsh`에서는 `?`가 glob으로 해석될 수 있으니 URL은 따옴표로 감싸는 편이 안전합니다.

```bash
curl "http://localhost:8004/api/boards/255679?limit=10"
```

응답 예시:

```json
{
  "board": {
    "id": "255679",
    "title": "비밀게시판",
    "url": "https://everytime.kr/255679"
  },
  "articles": [
    {
      "title": "스물다섯 스물하나",
      "href": "https://everytime.kr/255679/v/406323586",
      "author": "익명",
      "created_at": "2026-04-02 08:38:19",
      "preview": ".",
      "comment_count": "0",
      "like_count": "0"
    }
  ]
}
```

파라미터:

- `limit`: 1 이상 100 이하, 기본값 `20`

### 디버그

```bash
curl http://localhost:8004/api/debug/boards/255679
```

용도:

- 게시판 HTML 원문 일부 확인
- 게시판 XML API 응답 일부 확인
- 파서가 안 맞을 때 구조 확인

### 강의실

```bash
curl http://localhost:8004/api/lectures/mine
curl http://localhost:8004/api/lectures/points
curl "http://localhost:8004/api/lectures/search?keyword=컴퓨터그래픽스"
curl "http://localhost:8004/api/lectures/reviews/recent?limit=10"
curl http://localhost:8004/api/lectures/1768678
curl "http://localhost:8004/api/lectures/1768678/reviews?limit=10"
```

참고:

- `/api/lectures/mine`, `/api/lectures/points`, `/api/lectures/reviews/recent`는 로그인 쿠키가 필요한 에브리타임 API를 사용합니다.
- `/api/lectures/search`는 시간표 과목 검색 API를 사용하며, 가능한 경우 `lecture_id`와 평점 관련 필드를 함께 반환합니다.
- `/api/lectures/{lecture_id}`는 쿠키 없이 공개 강의 페이지 메타데이터만 조회합니다.
- `/api/lectures/{lecture_id}/reviews`는 기본적으로 쿠키 없이 강의평 API를 호출합니다. 에브리타임 응답이 성공이 아니면 공개 강의 페이지 메타데이터와 실패 정보를 함께 반환합니다.

### 시간표

```bash
curl http://localhost:8004/api/timetable/semesters
curl "http://localhost:8004/api/timetable/tables?year=2026&semester=1"
curl http://localhost:8004/api/timetable/tables/57033267
curl http://localhost:8004/api/timetable/current
```

응답에는 시간표 메타데이터, 과목 목록, 요일/시작/종료/장소 단위 수업 시간이 포함됩니다.

## MCP 서버

FastMCP는 공식 Python SDK의 Streamable HTTP 방식으로 구성했습니다.
공식 SDK 문서 기준으로 `stateless_http=True`, `json_response=True` 패턴을 사용했습니다.

공식 참고:

- https://github.com/modelcontextprotocol/python-sdk

접속 주소:

- 로컬 호스트: `http://localhost:8004/mcp`
- 같은 docker-compose 네트워크 내부: `http://everytime-mcp:8004/mcp`

헬스체크:

- 로컬 호스트: `http://localhost:8004/healthz`
- 같은 docker-compose 네트워크 내부: `http://everytime-mcp:8004/healthz`

현재 제공 tool:

- `health_check`
- `get_home_summary`
- `list_boards`
- `get_board_posts`
- `debug_board`
- `get_my_lectures`
- `get_lecture_points`
- `search_lectures`
- `get_recent_lecture_reviews`
- `get_lecture_reviews`
- `get_public_lecture_page`
- `list_timetable_semesters`
- `list_timetable_tables`
- `get_timetable`
- `get_current_timetable`

예상 매핑:

- `list_boards` -> 게시판 목록 조회
- `get_board_posts(board_id, limit)` -> 게시판 글 목록 조회
- `get_home_summary()` -> 홈 요약 조회
- `search_lectures(keyword, year, semester, limit, offset)` -> 강의/과목 검색
- `get_lecture_reviews(lecture_id, limit, offset, use_cookie)` -> 강의평/평점 조회
- `get_current_timetable()` -> 현재 학기 대표 시간표 조회

## docker-compose

`docker-compose.yml`은 Everytime MCP 서비스를 `8004` 포트로 올립니다.

- `everytime-mcp`

같은 compose 네트워크 이름은 `everytime-net`이며, 다른 컨테이너에서는 서비스명으로 접근하는 편이 안전합니다.

예시:

```env
EVERYTIME_MCP_URL=http://everytime-mcp:8004/mcp
EVERYTIME_API_URL=http://everytime-mcp:8004
```

`host.docker.internal`은 로컬 개발 환경에 따라 동작 차이가 있으므로, 같은 compose 네트워크 안에서는 권장하지 않습니다.
현재 MCP 앱은 다음 Host 헤더를 명시적으로 허용합니다.

- `localhost`
- `127.0.0.1`
- `everytime-mcp`
- `host.docker.internal`

또한 `/mcp`로 들어오는 요청은 내부에서 `localhost:8004` Host로 정규화해서 FastMCP 내부 Host 검증과 충돌하지 않도록 처리합니다.

## 트러블슈팅

### 로그인 페이지가 나온다

원인:

- 쿠키 만료
- 필요한 쿠키 일부 누락

대응:

- 브라우저에서 `Cookie` 헤더 전체를 다시 복사
- `.env` 갱신 후 컨테이너 재시작

### `zsh: no matches found`

원인:

- `?limit=10` 같은 쿼리스트링을 따옴표 없이 입력함

대응:

```bash
curl "http://localhost:8004/api/boards/255679?limit=10"
```

### 게시판 글 목록이 비어 있다

대응:

- `GET /api/debug/boards/{board_id}` 호출
- `api_preview`에 XML이 내려오는지 확인

### MCP가 안 붙는다

확인 순서:

1. 로컬에서 MCP 헬스체크 확인

```bash
curl http://localhost:8004/healthz
```

2. 같은 compose 네트워크 안의 다른 컨테이너에서는 서비스명으로 접근

```bash
curl http://everytime-mcp:8004/healthz
curl http://everytime-mcp:8004/mcp
```

3. 다른 컨테이너 환경 변수는 가능하면 이렇게 설정

```env
EVERYTIME_MCP_URL=http://everytime-mcp:8004/mcp
```

### XML 파서 에러가 난다

원인:

- `lxml` 미설치

대응:

- 이미 `requirements.txt`에 포함되어 있으므로 이미지 재빌드

## 주의

- 쿠키가 만료되면 수동으로 다시 넣어야 합니다.
- 에브리타임 웹 구조나 내부 API 경로가 바뀌면 수정이 필요할 수 있습니다.
- 현재는 읽기 전용 조회 서버입니다.
