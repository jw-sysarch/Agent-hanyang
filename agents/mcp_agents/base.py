import os
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from google.adk.agents import Agent
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

from agents.common.instructions import load_instruction_provider
from agents.common.models import build_model


def join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def get_mcp_endpoint(name: str, env_var: str) -> dict[str, str]:
    return {
        "name": name,
        "url": os.getenv(env_var, ""),
        "status": "configured" if os.getenv(env_var) else "missing",
    }


def build_health_tool(
    *,
    name: str,
    env_var: str,
    default_base_url: str,
    health_path: str,
):
    def check_mcp_server_health() -> dict[str, Any]:
        base_url = os.getenv(env_var, default_base_url)
        url = join_url(base_url, health_path)
        request = Request(url, headers={"Accept": "application/json"})

        try:
            with urlopen(request, timeout=5) as response:
                body = response.read().decode("utf-8", errors="replace")
                try:
                    payload = json.loads(body)
                except json.JSONDecodeError:
                    payload = {"body": body}
                return {
                    "name": name,
                    "url": url,
                    "status_code": response.status,
                    "ok": 200 <= response.status < 300,
                    "response": payload,
                }
        except HTTPError as exc:
            return {
                "name": name,
                "url": url,
                "status_code": exc.code,
                "ok": False,
                "error": exc.reason,
            }
        except URLError as exc:
            return {
                "name": name,
                "url": url,
                "ok": False,
                "error": str(exc.reason),
            }
        except TimeoutError:
            return {
                "name": name,
                "url": url,
                "ok": False,
                "error": "Request timed out",
            }

    check_mcp_server_health.__name__ = f"check_{name}_mcp_health"
    return check_mcp_server_health


def build_mcp_agent(
    *,
    name: str,
    env_var: str,
    default_base_url: str,
    description: str,
    instruction_module: str,
    health_path: str = "/healthz",
    tools: list[Any] | None = None,
    sub_agents: list[Agent] | None = None,
) -> Agent:
    def describe_endpoint() -> dict[str, str]:
        return get_mcp_endpoint(name, env_var)

    describe_endpoint.__name__ = f"get_{name}_mcp_endpoint"
    base_url = os.getenv(env_var, default_base_url)
    mcp_url = join_url(base_url, os.getenv("MCP_STREAMABLE_PATH", "/mcp"))

    active_tools = [
        describe_endpoint,
        build_health_tool(
            name=name,
            env_var=env_var,
            default_base_url=default_base_url,
            health_path=health_path,
        ),
        McpToolset(connection_params=StreamableHTTPConnectionParams(url=mcp_url)),
    ]
    if tools:
        active_tools.extend(tools)

    return Agent(
        name=name,
        model=build_model(),
        description=description,
        instruction=load_instruction_provider(instruction_module),
        tools=active_tools,
        sub_agents=sub_agents or [],
    )
