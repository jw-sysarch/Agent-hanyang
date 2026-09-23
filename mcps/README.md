# MCP Services

Each folder owns one MCP service boundary.

- `app.py`: service entrypoint. Replace the placeholder FastAPI app with the migrated MCP server implementation.
- `Dockerfile`: container definition for that MCP.
- `.env.<name>.example`: safe defaults and required variable names.
- `.env.<name>`: local secret file, ignored by git.

Current services:

- `gmail`
- `google_docs`
- `google_sheets`
- `google_calendar`
- `everytime`
- `naver_clova`
- `kakao_map`

The root ADK agent reads service URLs from root `.env.example` and delegates to matching sub-agents under `agents/mcp_agents`.
