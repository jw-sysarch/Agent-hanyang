import os

from google.adk.agents import Agent

from agents.common.instructions import load_instruction_provider
from agents.common.models import build_model
from agents.mcp_agents import (
    build_everytime_agent,
    build_gmail_agent,
    build_google_calendar_agent,
    build_google_docs_agent,
    build_google_sheets_agent,
    build_kakao_map_agent,
    build_naver_clova_agent,
)


root_agent = Agent(
    name=os.getenv("APP_NAME", "root_agent"),
    model=build_model(),
    description="Root coordinator that delegates user requests to MCP-specific agents.",
    instruction=load_instruction_provider("root_agent.root"),
    sub_agents=[
        build_gmail_agent(),
        build_google_docs_agent(),
        build_google_sheets_agent(),
        build_google_calendar_agent(),
        build_everytime_agent(),
        build_naver_clova_agent(),
        build_kakao_map_agent(),
    ],
)
