"""Scenario 8: OpenTelemetry out of the box.

Agent Framework emits GenAI semantic-convention spans for every agent run, model call and
tool call. Here we attach an in-memory exporter and print the span tree, so the audience
sees exactly what would land in Application Insights, Aspire Dashboard, Jaeger, Langfuse...
"""

from __future__ import annotations

from collections import defaultdict

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from .. import ui
from ..agents import concierge_agent
from ..runtime import chat_turn

TITLE = "Observability: OpenTelemetry spans for agents, models and tools"
NEEDS_LIVE = False

_configured = False


class ListExporter(SpanExporter):
    def __init__(self) -> None:
        self.spans: list[ReadableSpan] = []

    def export(self, spans) -> SpanExportResult:
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:  # pragma: no cover
        pass


EXPORTER = ListExporter()


def configure_once() -> None:
    global _configured
    if _configured:
        return
    from agent_framework.observability import configure_otel_providers

    configure_otel_providers(exporters=[EXPORTER], enable_sensitive_data=True, service_name="contoso-agents")
    _configured = True


def print_tree(spans: list[ReadableSpan]) -> list[str]:
    by_parent: dict[int | None, list[ReadableSpan]] = defaultdict(list)
    for s in spans:
        by_parent[s.parent.span_id if s.parent else None].append(s)
    lines: list[str] = []

    def walk(parent: int | None, depth: int) -> None:
        for s in sorted(by_parent.get(parent, []), key=lambda x: x.start_time or 0):
            ms = ((s.end_time or 0) - (s.start_time or 0)) / 1e6
            attrs = s.attributes or {}
            extra = []
            if "gen_ai.usage.input_tokens" in attrs:
                extra.append(f"tokens in={attrs['gen_ai.usage.input_tokens']} out={attrs.get('gen_ai.usage.output_tokens')}")
            if "gen_ai.tool.name" in attrs:
                extra.append(f"tool={attrs['gen_ai.tool.name']}")
            if "gen_ai.provider.name" in attrs and depth == 0:
                extra.append(f"provider={attrs['gen_ai.provider.name']}")
            line = f"{'  ' * depth}{s.name}  [{ms:.1f} ms]" + (f"  ({', '.join(extra)})" if extra else "")
            lines.append(line)
            walk(s.context.span_id, depth + 1)

    walk(None, 0)
    return lines


async def run(interactive: bool = False) -> dict:
    ui.banner(TITLE, "configure_otel_providers(exporters=[...]) then just run the agent")
    configure_once()
    start = len(EXPORTER.spans)

    agent = concierge_agent()
    session = agent.create_session()
    await chat_turn(agent, "Where is order ORD-1003 and what's in it?", session)

    from opentelemetry import trace

    provider = trace.get_tracer_provider()
    if hasattr(provider, "force_flush"):
        provider.force_flush()
    spans = EXPORTER.spans[start:]
    ui.section(f"Span tree ({len(spans)} spans, GenAI semantic conventions)")
    lines = print_tree(spans)
    for line in lines:
        print("  " + line)
    ui.note("Point OTEL_EXPORTER_OTLP_ENDPOINT at Aspire Dashboard or Application Insights to see this in a UI.")
    return {"span_names": [s.name for s in spans], "tree": lines}
