"""End-to-end runs of every offline scenario against the scripted model.

These tests exercise the real Agent Framework machinery (function invocation, approvals,
middleware, handoff and concurrent orchestration, checkpoints, telemetry); only the model
is scripted. Run: ``pytest -q``.
"""

from __future__ import annotations

import os

import pytest

os.environ["AGENT_PROVIDER"] = "offline"
os.environ["OFFLINE_DELAY"] = "0"
os.environ["NO_COLOR"] = "1"

from contoso_agents.scenarios import (  # noqa: E402
    checkpoint,
    concurrent,
    guardrails,
    handoff,
    harness,
    observability,
    single_agent,
    tool_approval,
)
from contoso_agents.tools import REFUNDS  # noqa: E402


async def test_single_agent_uses_tools_and_keeps_context():
    result = await single_agent.run()
    turns = result["turns"]
    assert "ORD-1001" in turns[0] and "shipped" in turns[0]
    assert "out of stock" in turns[1]
    assert "Trailhead" in turns[2]


async def test_tool_approval_runs_only_when_approved():
    before = len(REFUNDS)
    result = await tool_approval.run()
    assert "refund of $49.00" in result["approved"]
    assert "not issued" in result["declined"]
    assert len(REFUNDS) == before + 1
    assert REFUNDS[-1]["order_id"] == "ORD-1002"


async def test_guardrails_block_pii_and_audit_tools():
    result = await guardrails.run()
    assert "card numbers" in result["blocked"]
    assert "Invoice for ORD-1002" in result["allowed"]
    assert result["model_calls"] == 2, "blocked turn must never reach the model"
    assert [e["tool"] for e in result["audit"]] == ["get_invoice"]


async def test_handoff_routes_between_specialists_with_approval():
    before = len(REFUNDS)
    result = await handoff.run()
    agents = result["agents"]
    assert agents[0] == "triage"
    assert "orders" in agents and "billing" in agents
    assert agents.index("orders") < agents.index("billing")
    assert len(REFUNDS) == before + 1


async def test_concurrent_panel_streams_experts_and_aggregates():
    result = await concurrent.run()
    assert set(result["experts"]) == {"researcher", "marketer", "legal"}
    assert result["final"] and "Launch brief" in result["final"]


async def test_harness_agent_injects_planning_tools():
    result = await harness.run()
    assert "TodoProvider" in result["providers"]
    assert "todos_add" in result["tools"] and "file_memory_write" in result["tools"]
    assert "Hero product" in result["text"]


async def test_checkpoint_pause_and_resume(tmp_path):
    before = len(REFUNDS)
    result = await checkpoint.run(storage_dir=str(tmp_path))
    assert result["approvals"] == 1
    assert result["checkpoints"] >= 1
    assert len(REFUNDS) == before + 1
    assert any(p.suffix == ".json" for p in tmp_path.iterdir())


async def test_observability_emits_genai_spans():
    result = await observability.run()
    names = result["span_names"]
    assert any(n.startswith("invoke_agent") for n in names)
    assert any(n.startswith("chat") for n in names)
    assert any(n.startswith("execute_tool") for n in names)


@pytest.mark.parametrize("name", ["agent", "handoff", "concurrent"])
def test_cli_lists_scenarios(name, capsys):
    from contoso_agents.__main__ import main

    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert name in out
