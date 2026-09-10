"""Command line entry point.

    python -m contoso_agents list
    python -m contoso_agents agent            # run one scenario
    python -m contoso_agents handoff -i       # interactive: you type the customer's messages
    python -m contoso_agents all              # run every scenario that works with the current provider
    python -m contoso_agents devui            # open the DevUI web app
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from . import __version__, ui
from .config import describe_provider, is_live
from .scenarios import SCENARIOS, load


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="contoso-agents", description="Microsoft Agent Framework showcase")
    parser.add_argument("scenario", nargs="?", default="list", help="scenario name, 'all', 'list' or 'devui'")
    parser.add_argument("-i", "--interactive", action="store_true", help="type the customer's messages yourself")
    parser.add_argument("--port", type=int, default=8080, help="DevUI port")
    args = parser.parse_args(argv)

    print(f"contoso-agents {__version__}  |  provider: {describe_provider()}")

    if args.scenario == "list":
        print()
        for key in SCENARIOS:
            module = load(key)
            tag = " (needs a real model)" if module.NEEDS_LIVE and not is_live() else ""
            tag = tag or (" (needs network)" if getattr(module, "NEEDS_NETWORK", False) else "")
            print(f"  {key:<11} {module.TITLE}{tag}")
        print("\n  all         run every scenario available with the current provider")
        print("  devui       open the DevUI web app on http://127.0.0.1:8080")
        return 0

    if args.scenario == "devui":
        from .devui_app import main as devui_main

        devui_main(port=args.port)
        return 0

    names = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    for name in names:
        if name not in SCENARIOS:
            print(f"unknown scenario {name!r}; try 'list'", file=sys.stderr)
            return 2
        module = load(name)
        if args.scenario == "all" and (module.NEEDS_LIVE and not is_live() or getattr(module, "NEEDS_NETWORK", False)):
            ui.note(f"skipping {name}: {module.TITLE}")
            continue
        asyncio.run(module.run(interactive=args.interactive))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
