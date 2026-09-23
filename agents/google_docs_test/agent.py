from google.adk.agents import Agent

from agents.common.instructions import load_instruction
from agents.common.models import build_model
from agents.mcp_agents.google_docs import build_google_docs_agent


root_agent = Agent(
    name="google_docs_test",
    model=build_model(),
    description="Focused web-test agent for Google Docs and Drive MCP tools.",
    instruction=load_instruction("mcp.google_docs.root"),
    sub_agents=[build_google_docs_agent()],
)
