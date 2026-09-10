"""Scenario 4: handoff orchestration.

Triage receives the customer and hands off to the orders, billing or product specialist.
Specialists hand back to triage when a request is outside their remit. The refund tool
inside billing still requires approval, so the same event loop handles both "the agent
needs the user" and "the agent needs a human approval".
"""

from __future__ import annotations

from collections.abc import Callable

from agent_framework import AgentResponseUpdate, Content, WorkflowEvent
from agent_framework.orchestrations import HandoffAgentUserRequest, HandoffBuilder

from .. import ui
from ..agents import billing_agent, orders_agent, product_agent, triage_agent
from ..runtime import auto_approve, console_approver

TITLE = "Handoff orchestration: triage -> specialists"
NEEDS_LIVE = False

SCRIPTED_TURNS = [
    "Hi, where is my order ORD-1001?",
    "Thanks. Also, I think I was charged twice for ORD-1002, can I get a $49 refund?",
    "Perfect, that's all.",
]


def build_workflow(checkpoint_storage=None):
    triage, orders, billing, product = triage_agent(), orders_agent(), billing_agent(), product_agent()
    builder = HandoffBuilder(
        name="contoso_support",
        participants=[triage, orders, billing, product],
        checkpoint_storage=checkpoint_storage,
    ).with_start_agent(triage)
    # Triage can route anywhere; specialists only hand back to triage.
    builder.add_handoff(triage, [orders, billing, product])
    builder.add_handoff(orders, [triage])
    builder.add_handoff(billing, [triage])
    builder.add_handoff(product, [triage])
    return builder.build()


async def drive(
    workflow,
    turns: list[str],
    *,
    interactive: bool,
    approver: Callable[[Content], bool],
    first_message: str | None = None,
) -> list[tuple[str, str]]:
    """Run the workflow until the customer is done. Returns [(agent, text), ...]."""
    transcript: list[tuple[str, str]] = []
    queue = list(turns)

    async def consume(stream) -> list[WorkflowEvent]:
        pending: list[WorkflowEvent] = []
        current: str | None = None
        buffer: list[str] = []

        def flush() -> None:
            if current and buffer:
                transcript.append((current, "".join(buffer)))
                ui.stream_end()

        async for event in stream:
            if event.type in ("output", "intermediate") and isinstance(event.data, AgentResponseUpdate):
                if event.data.text:
                    if event.executor_id != current:
                        flush()
                        current, buffer = event.executor_id, []
                        ui.stream_start(current)
                    ui.stream_chunk(event.data.text)
                    buffer.append(event.data.text)
                for content in event.data.contents:
                    if content.type == "function_call" and content.name.startswith("handoff_to_"):
                        flush()
                        buffer = []
                        ui.handoff(event.executor_id, content.name.removeprefix("handoff_to_"))
            elif event.type == "request_info":
                pending.append(event)
        flush()
        return pending

    opening = first_message or (queue.pop(0) if queue else ui.ask("You: "))
    ui.user(opening)
    pending = await consume(workflow.run(opening, stream=True))

    while pending:
        responses: dict[str, object] = {}
        for request in pending:
            data = request.data
            if isinstance(data, HandoffAgentUserRequest):
                if queue:
                    text = queue.pop(0)
                    ui.user(text)
                elif interactive:
                    text = ui.ask("You: ").strip()
                else:
                    text = "exit"
                if text.lower() in ("exit", "quit", "", "perfect, that's all."):
                    responses[request.request_id] = HandoffAgentUserRequest.terminate()
                else:
                    responses[request.request_id] = HandoffAgentUserRequest.create_response(text)
            elif isinstance(data, Content) and data.type == "function_approval_request":
                call = data.function_call
                if approver is not console_approver:
                    ui.approval_request(call.name, call.parse_arguments() or {})
                approved = approver(data)
                ui.approval_decision(approved)
                responses[request.request_id] = data.to_function_approval_response(approved=approved)
        pending = await consume(workflow.run(responses=responses, stream=True))

    return transcript


async def run(interactive: bool = False) -> dict:
    ui.banner(TITLE, "HandoffBuilder + add_handoff + request_info events + tool approval inside a workflow")
    ui.note("Triage -> orders for tracking, back to triage, -> billing for a refund that needs approval.")

    workflow = build_workflow()
    turns = [] if interactive else SCRIPTED_TURNS
    transcript = await drive(
        workflow, turns, interactive=interactive, approver=console_approver if interactive else auto_approve
    )
    return {"transcript": transcript, "agents": [a for a, _ in transcript]}
