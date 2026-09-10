"""Scenario 1: one agent, tools, a session that remembers, streaming output."""

from __future__ import annotations

from .. import ui
from ..agents import concierge_agent
from ..runtime import chat_turn

TITLE = "Single agent with tools, memory and streaming"
NEEDS_LIVE = False

TURNS = [
    "Hi! Where is my order ORD-1001?",
    "Great. And is the Basecamp 4-person tent (TNT-300) in stock?",
    "OK, what tents do you recommend instead?",
]


async def run(interactive: bool = False) -> dict:
    ui.banner(TITLE, "Agent + @tool functions + AgentSession + run(stream=True)")
    ui.note("The concierge has four tools. Watch it pick the right one per turn and keep context across turns.")

    agent = concierge_agent()
    session = agent.create_session()
    transcript: list[str] = []

    turns = TURNS if not interactive else []
    for text in turns:
        transcript.append(await chat_turn(agent, text, session))

    if interactive:
        ui.note("Type a message, or 'exit' to finish.")
        while True:
            text = ui.ask("You: ").strip()
            if text.lower() in ("exit", "quit", ""):
                break
            transcript.append(await chat_turn(agent, text, session, show_user=False))

    return {"turns": transcript}
