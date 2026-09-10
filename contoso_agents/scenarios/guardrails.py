"""Scenario 3: middleware as policy.

* PiiGuardMiddleware (agent middleware) blocks a card number before the model is called.
* audit_tool_calls (function middleware) records every tool call with timing.
* count_model_calls (chat middleware) counts model round-trips.
"""

from __future__ import annotations

from .. import ui
from ..agents import guarded_billing_agent
from ..middleware import AUDIT_LOG, MODEL_CALLS
from ..runtime import chat_turn

TITLE = "Guardrails and audit with middleware"
NEEDS_LIVE = False


async def run(interactive: bool = False) -> dict:
    ui.banner(TITLE, "AgentMiddleware + @function_middleware + @chat_middleware")

    agent = guarded_billing_agent()
    session = agent.create_session()
    audit_before, calls_before = len(AUDIT_LOG), len(MODEL_CALLS)

    blocked = await chat_turn(agent, "Refund my card 4111 1111 1111 1111 for order ORD-1002 please.", session)
    allowed = await chat_turn(agent, "Sorry. Can you show me the invoice for ORD-1002?", session)

    ui.section("What the middleware saw")
    ui.note(f"model calls: {len(MODEL_CALLS) - calls_before} (the blocked turn never reached the model)")
    for entry in AUDIT_LOG[audit_before:]:
        ui.note(f"audit: {entry['tool']} {entry['arguments']} -> {entry['duration_ms']} ms")

    return {
        "blocked": blocked,
        "allowed": allowed,
        "model_calls": len(MODEL_CALLS) - calls_before,
        "audit": AUDIT_LOG[audit_before:],
    }
