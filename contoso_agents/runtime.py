"""Shared helpers for running agents and workflows from the scenarios."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agent_framework import Agent, AgentSession, Content, Message

from . import ui

Approver = Callable[[Content], bool]


def auto_approve(_: Content) -> bool:
    return True


def auto_decline(_: Content) -> bool:
    return False


def console_approver(request: Content) -> bool:
    call = request.function_call
    ui.approval_request(call.name, call.parse_arguments() or {})
    answer = ui.ask("  Approve? [y/N] ").strip().lower()
    return answer in ("y", "yes")


def describe_approval(request: Content) -> tuple[str, dict[str, Any]]:
    call = request.function_call
    return call.name, dict(call.parse_arguments() or {})


async def chat_turn(
    agent: Agent,
    text: str | list[Message],
    session: AgentSession,
    *,
    approver: Approver = auto_approve,
    show_user: bool = True,
) -> str:
    """Stream one turn, resolving any tool-approval requests, and return the final text."""
    if show_user and isinstance(text, str):
        ui.user(text)

    collected: list[str] = []
    pending = text
    while True:
        started = False
        stream = agent.run(pending, session=session, stream=True)
        async for update in stream:
            if update.text:
                if not started:
                    ui.stream_start(agent.name or "agent")
                    started = True
                ui.stream_chunk(update.text)
                collected.append(update.text)
        if started:
            ui.stream_end()
        response = await stream.get_final_response()

        if not response.user_input_requests:
            return "".join(collected)

        replies: list[Message] = []
        for request in response.user_input_requests:
            name, args = describe_approval(request)
            if approver is not console_approver:
                ui.approval_request(name, args)
            approved = approver(request)
            ui.approval_decision(approved)
            replies.append(Message("user", [request.to_function_approval_response(approved)]))
        pending = replies
