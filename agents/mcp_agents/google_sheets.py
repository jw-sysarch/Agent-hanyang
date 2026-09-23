from google.adk.agents import Agent

from agents.mcp_agents.base import build_mcp_agent


def build_google_sheets_agent() -> Agent:
    return build_mcp_agent(
        name="google_sheets_agent",
        env_var="GOOGLE_SHEETS_MCP_URL",
        default_base_url="http://mcp-google-sheets:8003",
        description="Handles Google Sheets lookup, update, and analysis workflows.",
        instruction_module="mcp.google_sheets.root",
    )
