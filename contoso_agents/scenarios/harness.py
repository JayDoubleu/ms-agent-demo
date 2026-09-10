"""Scenario 6: the Harness agent (new in 2026).

``create_harness_agent`` returns a normal ``Agent`` pre-wired for long, multi-step work:
todo tracking, plan/execute modes, session file memory, context compaction, standing tool
approvals and OpenTelemetry. You bring the chat client and your own tools.
"""

from __future__ import annotations

from agent_framework import create_harness_agent

from .. import ui
from ..config import make_client
from ..runtime import chat_turn
from ..tools import check_inventory, search_products

TITLE = "Harness agent: batteries-included long-running work"
NEEDS_LIVE = False

TASK = (
    "Plan a spring hiking gear campaign. Check what tents, jackets and packs we have in stock, "
    "pick a hero product and a bundle, then give me a short campaign brief."
)


def build_agent():
    client = make_client("assistant")
    return client, create_harness_agent(
        client=client,
        name="campaign-planner",
        harness_instructions="Plan first with the todo tool, then execute. Report verified facts only.",
        agent_instructions="You are a Contoso Retail merchandising analyst.",
        tools=[search_products, check_inventory],
        disable_web_search=True,
    )


async def run(interactive: bool = False) -> dict:
    ui.banner(TITLE, "create_harness_agent(client=..., tools=[...])")
    client, agent = build_agent()
    providers = [type(p).__name__ for p in getattr(agent, "context_providers", [])]
    ui.note("Context providers wired by the harness: " + ", ".join(providers))

    session = agent.create_session()
    task = TASK
    if interactive:
        typed = ui.ask("Task (enter for default): ").strip()
        task = typed or TASK
    text = await chat_turn(agent, task, session)
    tool_names = list(getattr(client, "seen_tools", []))
    if tool_names:
        ui.section("Tools the model could see (yours + harness-injected)")
        ui.note(", ".join(tool_names))
    return {"text": text, "tools": tool_names, "providers": providers}
