from google.adk.agents import Agent

from agents.mcp_agents.base import build_mcp_agent


def build_google_calendar_agent() -> Agent:
    return build_mcp_agent(
        name="google_calendar_agent",
        env_var="GOOGLE_CALENDAR_MCP_URL",
        default_base_url="http://mcp-google-calendar:8002",
        description="Handles Google Calendar availability, scheduling, and event workflows.",
        instruction_module="mcp.google_calendar.root",
    )
