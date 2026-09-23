from google.adk.agents import Agent

from agents.mcp_agents.base import build_mcp_agent


def build_kakao_map_agent() -> Agent:
    return build_mcp_agent(
        name="kakao_map_agent",
        env_var="KAKAO_MAP_MCP_URL",
        default_base_url="http://mcp-kakao-map:8006",
        description="Handles Kakao Map place search, routing, and location workflows.",
        instruction_module="mcp.kakao_map.root",
    )
