"""Scenario 10: Magentic orchestration (Magentic-One style manager).

A manager agent plans, picks the next specialist each round, tracks progress in a ledger,
replans on stalls and synthesises the final answer. Optional human plan review.
Needs a real model: the manager's ledgers are structured JSON that the offline script does
not reproduce.
"""

from __future__ import annotations

import json

from agent_framework import AgentResponseUpdate, Message
from agent_framework.orchestrations import MagenticBuilder, MagenticPlanReviewRequest, MagenticProgressLedger

from .. import ui
from ..agents import legal_agent, marketer_agent, product_agent, researcher_agent
from ..config import is_live, make_client

TITLE = "Magentic orchestration: manager-led dynamic collaboration"
NEEDS_LIVE = True

TASK = (
    "Design a spring hiking campaign for Contoso Retail. Use the product specialist to find what is in stock, "
    "the researcher for market context, the marketer for the offer, and legal for compliance. "
    "Deliver a one-page brief with a hero product, a bundle, three campaign angles and a compliance checklist."
)


def build_workflow(plan_review: bool):
    from agent_framework import Agent

    manager = Agent(
        client=make_client("manager"),
        id="manager",
        name="manager",
        description="Coordinates the campaign team",
        instructions="You coordinate a team to complete complex tasks efficiently.",
    )
    participants = [product_agent(), researcher_agent(), marketer_agent(), legal_agent()]
    return MagenticBuilder(
        participants=participants,
        intermediate_output_from=participants,
        manager_agent=manager,
        enable_plan_review=plan_review,
        max_round_count=10,
        max_stall_count=2,
        max_reset_count=1,
    ).build()


async def run(interactive: bool = False) -> dict:
    ui.banner(TITLE, "MagenticBuilder(manager_agent=..., enable_plan_review=...)")
    if not is_live():
        ui.note("Magentic needs a real model. Set a provider in .env and run again.")
        return {"skipped": True}

    workflow = build_workflow(plan_review=interactive)
    ui.user(TASK)

    pending_request = None
    pending_responses = None
    final = None
    while final is None:
        stream = workflow.run(stream=True, responses=pending_responses) if pending_responses else workflow.run(TASK, stream=True)
        current = None
        async for event in stream:
            if event.type in ("intermediate", "output") and isinstance(event.data, AgentResponseUpdate):
                if event.data.text:
                    if event.executor_id != current:
                        if current:
                            ui.stream_end()
                        current = event.executor_id
                        ui.stream_start(current)
                    ui.stream_chunk(event.data.text)
            elif event.type == "magentic_orchestrator":
                if current:
                    ui.stream_end()
                    current = None
                ui.section(f"manager: {event.data.event_type.name}")
                content = event.data.content
                if isinstance(content, Message):
                    print(content.text)
                elif isinstance(content, MagenticProgressLedger):
                    print(json.dumps(content.to_dict(), indent=2))
            elif event.type == "request_info" and event.request_type is MagenticPlanReviewRequest:
                pending_request = event
        if current:
            ui.stream_end()

        result = await stream.get_final_response()
        outputs = result.get_outputs()
        if outputs:
            final = outputs[-1]
        pending_responses = None

        if pending_request is not None:
            data = pending_request.data
            ui.section("Plan review")
            print(data.plan.text)
            reply = ui.ask("Press enter to approve, or type feedback to revise: ").strip()
            pending_responses = {pending_request.request_id: data.approve() if not reply else data.revise(reply)}
            pending_request = None

    ui.section("Final brief")
    print(getattr(final, "text", final))
    return {"final": str(getattr(final, "text", final))}
