"""Demo scenarios. Each module exposes TITLE, NEEDS_LIVE and ``async run(interactive: bool)``."""

from __future__ import annotations

import importlib
from types import ModuleType

SCENARIOS: dict[str, str] = {
    "agent": "single_agent",
    "approval": "tool_approval",
    "guardrails": "guardrails",
    "handoff": "handoff",
    "concurrent": "concurrent",
    "harness": "harness",
    "checkpoint": "checkpoint",
    "trace": "observability",
    "mcp": "mcp",
    "magentic": "magentic",
}


def load(name: str) -> ModuleType:
    module = SCENARIOS[name]
    return importlib.import_module(f"{__name__}.{module}")
