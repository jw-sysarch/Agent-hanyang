# HAI MCP Agent Runtime

Google ADK 기반 루트 에이전트와 여러 MCP 서버를 Docker Compose로 함께 관리하는 프로젝트입니다.

현재는 실제 MCP 구현을 이관하기 전 단계의 인프라 골격입니다. 각 MCP 폴더에는 placeholder `app.py`가 있고, 나중에 서비스별 구현을 해당 폴더 안으로 옮기면 됩니다.

## 구조

```text
.
├── agents
│   ├── agent.py
│   ├── common
│   ├── instructions
│   │   ├── root_agent/root.py
│   │   └── mcp/<mcp_name>/root.py
│   ├── mcp_agents
│   │   ├── gmail.py
│   │   ├── google_docs.py
│   │   ├── google_sheets.py
│   │   ├── google_calendar.py
│   │   ├── everytime.py
│   │   ├── naver_clova.py
│   │   └── kakao_map.py
│   └── root_agent/agent.py
├── mcps
│   ├── gmail
│   ├── google_docs
│   ├── google_sheets
│   ├── google_calendar
│   ├── everytime
│   ├── naver_clova
│   └── kakao_map
├── app.py
├── docker-compose.yml
├── Dockerfile              # ADK agent runtime image
└── start.sh
```

## 실행

```bash
cp .env.example .env
docker compose up --build
```

`docker compose up --build`는 agent와 MCP 서버를 모두 빌드합니다.

- `adk-agent`: 루트 `Dockerfile`로 빌드되는 Google ADK agent 런타임
- `mcp-gmail`: `mcps/gmail/Dockerfile`로 빌드
- `mcp-google-docs`: `mcps/google_docs/Dockerfile`로 빌드
- `mcp-google-sheets`: `mcps/google_sheets/Dockerfile`로 빌드
- `mcp-google-calendar`: `mcps/google_calendar/Dockerfile`로 빌드
- `mcp-everytime`: `mcps/everytime/Dockerfile`로 빌드
- `mcp-naver-clova`: `mcps/naver_clova/Dockerfile`로 빌드
- `mcp-kakao-map`: `mcps/kakao_map/Dockerfile`로 빌드

특정 서비스만 빌드할 수도 있습니다.

```bash
docker compose build adk-agent
docker compose build mcp-gmail
```

접속:

- ADK API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- MCP health 예시: `http://localhost:8008/healthz`

MCP 포트:

```text
agent: 8000
google docs + drive: 8001
google calendar: 8002
google sheets: 8003
everytime: 8004
naver clova: 8005
kakao map: 8006
naver map: 8007
gmail: 8008
```

## MCP 환경 변수

각 MCP는 자기 폴더 아래 환경 파일을 가집니다.

```bash
cp mcps/gmail/.env.gmail.example mcps/gmail/.env.gmail
cp mcps/google_docs/.env.google_docs.example mcps/google_docs/.env.google_docs
cp mcps/google_sheets/.env.google_sheets.example mcps/google_sheets/.env.google_sheets
cp mcps/google_calendar/.env.google_calendar.example mcps/google_calendar/.env.google_calendar
cp mcps/everytime/.env.everytime.example mcps/everytime/.env.everytime
cp mcps/naver_clova/.env.naver_clova.example mcps/naver_clova/.env.naver_clova
cp mcps/kakao_map/.env.kakao_map.example mcps/kakao_map/.env.kakao_map
```

`.env.*` 파일은 git에서 무시됩니다. `.env.*.example`만 저장소에 남깁니다.

## MCP별 Agent 추가 방법

MCP 서버가 이미 있고, 그 MCP를 담당하는 ADK agent만 추가할 때의 패턴입니다.

1. `agents/instructions/mcp/<name>/` 폴더를 만들고 `__init__.py`, `root.py`를 추가합니다.
2. `root.py`에 `INSTRUCTION = """..."""` 문자열을 정의합니다.
3. `agents/mcp_agents/<name>.py`에 `build_<name>_agent()` helper를 추가합니다.
4. `agents/mcp_agents/__init__.py`에서 helper를 export 합니다.
5. `agents/root_agent/agent.py`의 `sub_agents`에 `build_<name>_agent()` 호출을 추가합니다.
6. `.env.example`에 `<NAME>_MCP_URL`을 추가합니다.

```python
def build_gmail_agent() -> Agent:
    return build_mcp_agent(
        name="gmail_agent",
        env_var="GMAIL_MCP_URL",
        description="Handles Gmail search, reading, drafting, and sending workflows.",
        instruction_module="mcp.gmail.root",
)
```

instruction은 `agents/instructions/mcp/<name>/root.py`의 `INSTRUCTION` 문자열로 관리합니다.

최상위 agent는 `agents/root_agent/agent.py`에서 각 `build_*_agent()`를 호출해 `sub_agents`로 조립합니다.

## MCP 서버 추가 방법

새 MCP 서비스를 Docker Compose에 추가할 때의 패턴입니다.

1. `mcps/<name>/` 폴더를 만듭니다.
2. `mcps/<name>/app.py`를 추가합니다.
3. `mcps/<name>/Dockerfile`을 추가합니다.
4. `mcps/<name>/requirements.txt`에 해당 MCP 서버 실행에 필요한 패키지를 적습니다.
5. `mcps/<name>/.env.<name>.example`에 안전한 기본값과 필요한 환경 변수 이름을 적습니다.
6. `.env.<name>`은 로컬에서만 만들고 git에는 올리지 않습니다.
7. `docker-compose.yml`에 `mcp-<name>` 서비스를 추가합니다.
8. 루트 agent가 접근할 수 있게 `.env.example`과 `adk-agent.environment`에 `<NAME>_MCP_URL=http://mcp-<name>:<port>`를 추가합니다.

기본 placeholder 서버는 아래 형태를 따릅니다.

```python
import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

MCP_NAME = os.getenv("MCP_NAME", "<name>")
PORT = int(os.getenv("PORT", "<port>"))

app = FastAPI(title=f"{MCP_NAME} MCP")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"name": MCP_NAME, "status": "ok"}


if __name__ == "__main__":
    uvicorn.run("app:app", host=os.getenv("HOST", "0.0.0.0"), port=PORT)
```

## MCP Agent의 Sub-Agent 추가 방법

MCP 하나가 내부적으로 여러 역할을 가져야 할 때는 해당 MCP agent 파일 안에서 더 작은 sub-agent를 만들고, root MCP agent에 붙입니다.

예를 들어 Gmail agent 아래에 `gmail_search_agent`, `gmail_draft_agent`를 두려면:

1. `agents/instructions/mcp/gmail/search.py`, `agents/instructions/mcp/gmail/draft.py`를 추가합니다.
2. 각 파일에 `INSTRUCTION = """..."""`을 정의합니다.
3. `agents/mcp_agents/gmail.py`에서 하위 agent builder를 만듭니다.
4. `build_gmail_agent()`가 반환하는 root Gmail agent에 `sub_agents=[...]`를 넘깁니다.

```python
from google.adk.agents import Agent

from agents.common.instructions import load_instruction
from agents.common.models import build_model
from agents.mcp_agents.base import build_mcp_agent


def build_gmail_search_agent() -> Agent:
    return Agent(
        name="gmail_search_agent",
        model=build_model(),
        description="Searches and reads Gmail messages.",
        instruction=load_instruction("mcp.gmail.search"),
    )


def build_gmail_draft_agent() -> Agent:
    return Agent(
        name="gmail_draft_agent",
        model=build_model(),
        description="Drafts Gmail replies and new messages.",
        instruction=load_instruction("mcp.gmail.draft"),
    )


def build_gmail_agent() -> Agent:
    return build_mcp_agent(
        name="gmail_agent",
        env_var="GMAIL_MCP_URL",
        description="Coordinates Gmail workflows.",
        instruction_module="mcp.gmail.root",
        sub_agents=[
            build_gmail_search_agent(),
            build_gmail_draft_agent(),
        ],
    )
```

`build_mcp_agent()`는 `sub_agents` 인자를 지원하므로, MCP별 내부 역할이 늘어날 때 같은 패턴으로 확장하면 됩니다.

## MCP 구현 이관 위치

각 MCP 구현은 아래 파일을 시작점으로 옮기면 됩니다.

- Gmail: `mcps/gmail/app.py`
- Google Docs: `mcps/google_docs/app.py`
- Google Sheets: `mcps/google_sheets/app.py`
- Google Calendar: `mcps/google_calendar/app.py`
- Everytime: `mcps/everytime/app.py`
- Naver Clova: `mcps/naver_clova/app.py`
- Kakao Map: `mcps/kakao_map/app.py`

현재 placeholder 서버는 `/healthz`, `/manifest`만 제공합니다.

## ADK 실행 모드

기본은 API 모드입니다.

```env
ADK_SERVER_MODE=api
```

ADK Web UI가 필요하면 `.env`에서 바꿉니다.

```env
ADK_SERVER_MODE=web
```

Docker에서 Google ADK가 제공하는 Web UI로 바로 실행하려면 `web` 프로필의 `adk-web` 서비스를 사용합니다.

```bash
docker compose --profile web up --build adk-web
```

백그라운드 실행:

```bash
docker compose --profile web up --build -d adk-web
```

접속 주소:

- Web UI: `http://localhost:8000/dev-ui/`

## 로컬 직접 실행

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app:app --host 0.0.0.0 --port 8000
```
