"""Launch DevUI with the demo agents and workflows registered in memory.

    python -m contoso_agents devui

DevUI is Microsoft's sample web UI for exercising agents and workflows, with an
OpenAI-compatible Responses API underneath (so `openai` SDK clients can call your agents).
"""

from __future__ import annotations

import os

from .agents import billing_agent, concierge_agent
from .config import describe_provider
from .scenarios.concurrent import build_workflow as build_concurrent
from .scenarios.handoff import build_workflow as build_handoff


def main(port: int = 8080, auto_open: bool = True) -> None:
    from agent_framework.devui import serve

    print(f"Provider: {describe_provider()}")
    entities = [concierge_agent(), billing_agent(), build_handoff(), build_concurrent()]
    serve(
        entities=entities,
        port=port,
        auto_open=auto_open,
        auth_enabled=os.getenv("DEVUI_AUTH", "false").lower() == "true",
        instrumentation_enabled=True,
    )


if __name__ == "__main__":
    main()
