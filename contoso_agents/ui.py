"""Tiny console styling helpers. No third-party dependency so the demo stays lean."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

_COLOR = sys.stdout.isatty() and os.getenv("NO_COLOR") is None

_CODES = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "cyan": "\033[36m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "magenta": "\033[35m",
    "blue": "\033[34m",
    "red": "\033[31m",
}

AGENT_COLORS = ["cyan", "green", "magenta", "blue", "yellow"]
_agent_color: dict[str, str] = {}


def _c(text: str, *styles: str) -> str:
    if not _COLOR:
        return text
    return "".join(_CODES[s] for s in styles) + text + _CODES["reset"]


def banner(title: str, subtitle: str = "") -> None:
    width = 78
    print()
    print(_c("=" * width, "dim"))
    print(_c(f" {title}", "bold"))
    if subtitle:
        print(_c(f" {subtitle}", "dim"))
    print(_c("=" * width, "dim"))


def section(title: str) -> None:
    print()
    print(_c(f"--- {title} ", "bold") + _c("-" * max(0, 74 - len(title)), "dim"))


def note(text: str) -> None:
    print(_c(f"  {text}", "dim"))


def policy(text: str) -> None:
    print(_c(f"  [policy] {text}", "red"))


def user(text: str) -> None:
    print()
    print(_c("You: ", "bold") + text)


def agent_label(name: str) -> str:
    color = _agent_color.setdefault(name, AGENT_COLORS[len(_agent_color) % len(AGENT_COLORS)])
    return _c(f"{name}: ", "bold", color)


def agent_line(name: str, text: str) -> None:
    print(agent_label(name) + text)


def stream_start(name: str) -> None:
    print(agent_label(name), end="", flush=True)


def stream_chunk(text: str) -> None:
    print(text, end="", flush=True)


def stream_end() -> None:
    print(flush=True)


def tool_call(name: str, arguments: Any) -> None:
    try:
        args = arguments.model_dump() if hasattr(arguments, "model_dump") else arguments
        rendered = json.dumps(args, default=str)
    except Exception:  # pragma: no cover - defensive
        rendered = str(arguments)
    print(_c(f"  -> tool {name}({rendered})", "yellow"))


def render_result(result: Any) -> str:
    """Flatten a tool result (str, list[Content], object) to text."""
    if isinstance(result, list):
        return "".join(getattr(c, "text", None) or str(c) for c in result)
    return str(result)


def tool_result(name: str, result: Any, elapsed_ms: float) -> None:
    text = render_result(result)
    if len(text) > 160:
        text = text[:157] + "..."
    print(_c(f"  <- {name} in {elapsed_ms:.1f} ms: {text}", "dim"))


def approval_request(tool: str, arguments: Any) -> None:
    print(_c(f"  [approval needed] {tool} {json.dumps(arguments, default=str)}", "yellow", "bold"))


def approval_decision(approved: bool) -> None:
    print(_c(f"  [approval] {'APPROVED' if approved else 'DECLINED'} by human", "green" if approved else "red"))


def handoff(source: str, target: str) -> None:
    print(_c(f"  >> handoff {source} -> {target}", "magenta", "bold"))


def ask(prompt: str) -> str:
    return input(_c(prompt, "bold"))
