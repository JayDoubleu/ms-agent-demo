"""Cross-cutting policies as middleware.

Three middleware kinds exist in Agent Framework and this module shows one of each:

* agent middleware   - wraps a whole ``agent.run`` (PII guard, blocks before the model is called)
* function middleware - wraps every tool call (audit log with timing)
* chat middleware    - wraps every request to the model (call counter)
"""

from __future__ import annotations

import re
import time
from collections.abc import Awaitable, Callable

from collections.abc import AsyncIterable

from agent_framework import (
    AgentContext,
    AgentMiddleware,
    AgentResponse,
    AgentResponseUpdate,
    ChatContext,
    Content,
    ResponseStream,
    FunctionInvocationContext,
    Message,
    chat_middleware,
    function_middleware,
)

from . import ui

AUDIT_LOG: list[dict] = []
"""Every tool invocation seen by ``audit_tool_calls`` in this process."""

MODEL_CALLS: list[int] = []
"""Number of messages sent per model call, appended by ``count_model_calls``."""

_CARD_NUMBER = re.compile(r"\b(?:\d[ -]?){13,19}\b")


class PiiGuardMiddleware(AgentMiddleware):
    """Block requests that contain what looks like a payment card number.

    Runs before the model sees the message. Setting ``context.result`` and returning
    without calling ``call_next`` short-circuits the run with our own response.
    """

    async def process(self, context: AgentContext, call_next: Callable[[], Awaitable[None]]) -> None:
        last = context.messages[-1] if context.messages else None
        if last is not None and last.text and _CARD_NUMBER.search(last.text):
            ui.policy("PII guard blocked the request: a card number was detected, the model was never called.")
            reply = (
                "For your security I can't accept card numbers in chat. "
                "Please remove it, and I'll help with your refund using the order number instead."
            )
            if context.stream:

                async def _stream() -> AsyncIterable[AgentResponseUpdate]:
                    yield AgentResponseUpdate(role="assistant", contents=[Content.from_text(reply)])

                context.result = ResponseStream(_stream(), finalizer=AgentResponse.from_updates)
            else:
                context.result = AgentResponse(messages=[Message("assistant", [reply])])
            return
        await call_next()


@function_middleware
async def audit_tool_calls(context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]) -> None:
    """Record every tool call with its arguments, result and duration."""
    started = time.perf_counter()
    ui.tool_call(context.function.name, context.arguments)
    await call_next()
    elapsed_ms = (time.perf_counter() - started) * 1000
    AUDIT_LOG.append(
        {
            "tool": context.function.name,
            "arguments": _as_dict(context.arguments),
            "result": ui.render_result(context.result)[:200] if context.result is not None else None,
            "duration_ms": round(elapsed_ms, 2),
        }
    )
    ui.tool_result(context.function.name, context.result, elapsed_ms)


@chat_middleware
async def count_model_calls(context: ChatContext, call_next: Callable[[], Awaitable[None]]) -> None:
    """Count model round-trips. Runs once per model call, including tool-result follow-ups."""
    MODEL_CALLS.append(len(context.messages))
    await call_next()


def _as_dict(arguments) -> dict:
    if arguments is None:
        return {}
    if hasattr(arguments, "model_dump"):
        return arguments.model_dump()
    if isinstance(arguments, dict):
        return dict(arguments)
    return {"value": str(arguments)}
