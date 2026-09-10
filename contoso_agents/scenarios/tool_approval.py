"""Scenario 2: human-in-the-loop tool approval.

``issue_refund`` is declared with ``@tool(approval_mode="always_require")``. The agent
pauses, surfaces a ``function_approval_request``, and only runs the tool if a human says yes.
"""

from __future__ import annotations

from .. import ui
from ..agents import billing_agent
from ..runtime import auto_approve, auto_decline, chat_turn, console_approver
from ..tools import REFUNDS

TITLE = "Human-in-the-loop tool approval"
NEEDS_LIVE = False


async def run(interactive: bool = False) -> dict:
    ui.banner(TITLE, '@tool(approval_mode="always_require") + AgentResponse.user_input_requests')
    ui.note("First request is approved, second is declined. The tool only runs when approved.")

    agent = billing_agent()
    before = len(REFUNDS)

    session = agent.create_session()
    approver = console_approver if interactive else auto_approve
    approved_text = await chat_turn(
        agent, "I was charged twice for order ORD-1002. Please refund $49.", session, approver=approver
    )

    session = agent.create_session()
    approver = console_approver if interactive else auto_decline
    declined_text = await chat_turn(
        agent, "Refund me 200 dollars for ORD-1001, I changed my mind.", session, approver=approver
    )

    ui.section("Refund ledger")
    for r in REFUNDS[before:]:
        ui.note(f"{r['order_id']}: ${r['amount']:.2f} ({r['reason']})")
    if len(REFUNDS) == before:
        ui.note("no refunds issued")

    return {"approved": approved_text, "declined": declined_text, "refunds": REFUNDS[before:]}
