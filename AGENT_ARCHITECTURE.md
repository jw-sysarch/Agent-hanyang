# 에이전트 / MCP 아키텍처

## 1. 전체 그림

```text
Client / ADK Web / curl
        |
        v
FastAPI ADK Runtime
        |
        v
agents/root_agent.root_agent
        |
        +------------------+----------------------+----------------+
        |                  |                      |
        v                  v                      v
   gmail_agent       google_docs_agent       google_sheets_agent
        |                  |                      |
        v                  v                      v
   mcps/gmail       mcps/google_docs       mcps/google_sheets

        +------------------+----------------------+----------------+
        |                  |                      |
        v                  v                      v
google_calendar_agent  everytime_agent  naver_clova_agent  kakao_map_agent
        |                  |                      |          |
        v                  v                      v          v
mcps/google_calendar  mcps/everytime  mcps/naver_clova  mcps/kakao_map
```

## 2. 책임 분리

- `app.py`: Google ADK FastAPI 앱 부트스트랩.
- `agents/root_agent/agent.py`: MCP별 sub-agent를 조립하는 최상위 coordinator.
- `agents/mcp_agents/*.py`: MCP별 `build_<name>_agent()` helper.
- `agents/instructions/**/*.py`: agent instruction 문자열 모듈.
- `mcps/<name>/app.py`: MCP 서버 entrypoint. 현재는 placeholder이며 실제 구현 이관 대상.
- `docker-compose.yml`: ADK agent와 MCP 서비스 전체 실행 단위.

## 3. Agent 빌드 규칙

각 MCP agent는 다음 형태를 따릅니다.

```python
def build_<name>_agent() -> Agent:
    return build_mcp_agent(
        name="<name>_agent",
        env_var="<NAME>_MCP_URL",
        description="...",
        instruction_module="mcp.<name>.root",
    )
```

이 패턴을 유지하면 새 MCP를 추가할 때 수정 지점이 명확합니다.

1. `mcps/<name>/` 폴더 추가
2. `agents/instructions/mcp/<name>/root.py`에 `INSTRUCTION` 문자열 추가
3. `agents/mcp_agents/<name>.py`에 `build_<name>_agent()` 추가
4. `agents/mcp_agents/__init__.py` export 추가
5. `agents/root_agent/agent.py`의 `sub_agents`에 추가
6. `docker-compose.yml` 서비스와 `.env.example` MCP URL 추가

## 4. 환경 변수 규칙

루트 agent는 MCP URL만 압니다.

```env
GOOGLE_DOCS_MCP_URL=http://mcp-google-docs:8001
GOOGLE_CALENDAR_MCP_URL=http://mcp-google-calendar:8002
GOOGLE_SHEETS_MCP_URL=http://mcp-google-sheets:8003
EVERYTIME_MCP_URL=http://mcp-everytime:8004
NAVER_CLOVA_MCP_URL=http://mcp-naver-clova:8005
KAKAO_MAP_MCP_URL=http://mcp-kakao-map:8006
NAVER_MAP_MCP_URL=http://mcp-naver-map:8007
GMAIL_MCP_URL=http://mcp-gmail:8008
```

서비스별 인증정보는 각 MCP 폴더의 `.env.<name>`에 둡니다.

```text
mcps/gmail/.env.gmail
mcps/google_docs/.env.google_docs
mcps/google_sheets/.env.google_sheets
mcps/google_calendar/.env.google_calendar
mcps/everytime/.env.everytime
mcps/naver_clova/.env.naver_clova
mcps/kakao_map/.env.kakao_map
```

## 5. 현재 placeholder 상태

MCP 서버들은 아직 실제 MCP transport/tool 구현이 아니라 FastAPI placeholder입니다.

- `GET /healthz`: 컨테이너 생존 확인
- `GET /manifest`: 서비스 이름과 placeholder 상태 확인

실제 MCP 코드 이관 시에는 각 `mcps/<name>/app.py`를 교체하고, 필요 패키지는 해당 폴더의 `requirements.txt`에 추가하면 됩니다.
