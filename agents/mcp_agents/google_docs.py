from google.adk.agents import Agent

from agents.mcp_agents.base import build_mcp_agent


def build_google_docs_agent() -> Agent:
    return build_mcp_agent(
        name="google_docs_agent",
        env_var="GOOGLE_DOCS_MCP_URL",
        default_base_url="http://mcp-google-docs:8001",
        description="Handles Google Docs document lookup, reading, and editing workflows.",
        instruction_module="mcp.google_docs.root",
    )
