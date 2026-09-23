from google.adk.agents import Agent

from agents.mcp_agents.base import build_mcp_agent


def build_gmail_agent() -> Agent:
    return build_mcp_agent(
        name="gmail_agent",
        env_var="GMAIL_MCP_URL",
        default_base_url="http://mcp-gmail:8008",
        description="Handles Gmail search, reading, drafting, and sending workflows.",
        instruction_module="mcp.gmail.root",
    )
