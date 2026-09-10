"""Scenario 5: concurrent orchestration.

Three experts review the same brief in parallel; a summarizer agent aggregates their output
into one launch brief. Intermediate outputs stream as each expert finishes.
"""

from __future__ import annotations

from agent_framework import AgentExecutorResponse, AgentResponseUpdate
from agent_framework.orchestrations import ConcurrentBuilder

from .. import ui
from ..agents import legal_agent, marketer_agent, researcher_agent, summarizer_agent

TITLE = "Concurrent orchestration: expert panel with custom aggregator"
NEEDS_LIVE = False

BRIEF = "We are launching a spring hiking range: Trailhead tent, Summit rain jacket and Daybreak backpack. Review the launch."


def build_workflow():
    researcher, marketer, legal = researcher_agent(), marketer_agent(), legal_agent()
    summarizer = summarizer_agent()

    async def summarize(results: list[AgentExecutorResponse]) -> str:
        sections = []
        for r in results:
            messages = getattr(r.agent_response, "messages", [])
            final_text = messages[-1].text if messages else "(no content)"
            sections.append(f"## {r.executor_id}\n{final_text}")
        response = await summarizer.run("\n\n".join(sections))
        return response.text

    workflow = (
        ConcurrentBuilder(
            participants=[researcher, marketer, legal],
            intermediate_output_from=[researcher, marketer, legal],
        )
        .with_aggregator(summarize)
        .build()
    )
    workflow.name = "contoso_launch_panel"
    return workflow


async def run(interactive: bool = False) -> dict:
    ui.banner(TITLE, "ConcurrentBuilder + intermediate_output_from + with_aggregator")
    workflow = build_workflow()

    brief = BRIEF
    if interactive:
        typed = ui.ask("Launch brief (enter for default): ").strip()
        brief = typed or BRIEF
    ui.user(brief)

    experts: dict[str, list[str]] = {}
    current: str | None = None
    final: str | None = None
    async for event in workflow.run(brief, stream=True):
        if event.type == "intermediate" and isinstance(event.data, AgentResponseUpdate) and event.data.text:
            if event.executor_id != current:
                if current:
                    ui.stream_end()
                current = event.executor_id
                ui.stream_start(current)
            ui.stream_chunk(event.data.text)
            experts.setdefault(current, []).append(event.data.text)
        elif event.type == "output":
            final = str(event.data)
    if current:
        ui.stream_end()

    ui.section("Consolidated launch brief (summarizer)")
    print(final)
    return {"experts": {k: "".join(v) for k, v in experts.items()}, "final": final}
