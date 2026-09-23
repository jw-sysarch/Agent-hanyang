from google.adk.agents import Agent

from agents.mcp_agents.base import build_mcp_agent


def build_everytime_agent() -> Agent:
    return build_mcp_agent(
        name="everytime_agent",
        env_var="EVERYTIME_MCP_URL",
        default_base_url="http://mcp-everytime:8004",
        description="Handles Everytime timetable and campus community workflows.",
        instruction_module="mcp.everytime.root",
    )
