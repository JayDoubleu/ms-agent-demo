"""Scenario 9: Model Context Protocol tools.

The agent connects to the public Microsoft Learn MCP server over streamable HTTP and uses its
tools like any other function tool. Offline, the scripted model still calls the real MCP
tool, so this scenario needs network access but no API key.
"""

from __future__ import annotations

from agent_framework import Agent, MCPStreamableHTTPTool

from .. import ui
from ..config import make_client
from ..runtime import chat_turn

TITLE = "MCP: Microsoft Learn docs as tools"
NEEDS_LIVE = False
NEEDS_NETWORK = True

QUESTION = "Using Microsoft Learn, what is handoff orchestration in Microsoft Agent Framework? Two sentences."


async def run(interactive: bool = False) -> dict:
    ui.banner(TITLE, "MCPStreamableHTTPTool(url='https://learn.microsoft.com/api/mcp')")
    question = QUESTION
    if interactive:
        typed = ui.ask("Question (enter for default): ").strip()
        question = typed or QUESTION

    async with MCPStreamableHTTPTool(name="Microsoft Learn MCP", url="https://learn.microsoft.com/api/mcp") as learn:
        tool_names = [t.name for t in getattr(learn, "functions", [])]
        ui.note("MCP tools discovered: " + ", ".join(tool_names))
        agent = Agent(
            client=make_client("docs"),
            id="docs",
            name="docs",
            instructions="Answer Microsoft documentation questions using the Microsoft Learn tools. Cite the page title.",
            tools=learn,
        )
        session = agent.create_session()
        text = await chat_turn(agent, question, session)
    return {"text": text, "tools": tool_names}
