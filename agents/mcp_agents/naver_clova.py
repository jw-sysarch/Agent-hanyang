from google.adk.agents import Agent

from agents.mcp_agents.base import build_mcp_agent


def build_naver_clova_agent() -> Agent:
    return build_mcp_agent(
        name="naver_clova_agent",
        env_var="NAVER_CLOVA_MCP_URL",
        default_base_url="http://mcp-naver-clova:8005",
        health_path="/health",
        description="Handles Naver Clova speech and AI workflows.",
        instruction_module="mcp.naver_clova.root",
    )
