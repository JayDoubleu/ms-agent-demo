"""Scenario 7: durable workflows with checkpoints.

A refund request pauses the handoff workflow for approval. The process "exits". A second
process lists the checkpoints, restores the latest one, supplies the approval, and the
workflow completes. This is how approvals that take hours or days are handled.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from agent_framework import AgentResponseUpdate, Content, FileCheckpointStorage
from agent_framework.orchestrations import HandoffAgentUserRequest

from .. import ui
from ..tools import REFUNDS
from .handoff import build_workflow

TITLE = "Durable handoff with file checkpoints (pause, exit, resume)"
NEEDS_LIVE = False


async def _print_stream(stream) -> list:
    pending = []
    current = None
    async for event in stream:
        if event.type in ("output", "intermediate") and isinstance(event.data, AgentResponseUpdate):
            if event.data.text:
                if event.executor_id != current:
                    if current:
                        ui.stream_end()
                    current = event.executor_id
                    ui.stream_start(current)
                ui.stream_chunk(event.data.text)
            for c in event.data.contents:
                if c.type == "function_call" and c.name.startswith("handoff_to_"):
                    if current:
                        ui.stream_end()
                        current = None
                    ui.handoff(event.executor_id, c.name.removeprefix("handoff_to_"))
        elif event.type == "request_info":
            pending.append(event)
    if current:
        ui.stream_end()
    return pending


async def run(interactive: bool = False, storage_dir: str | None = None) -> dict:
    ui.banner(TITLE, "FileCheckpointStorage + workflow.run(checkpoint_id=..., responses=...)")
    path = Path(storage_dir or tempfile.mkdtemp(prefix="contoso-checkpoints-"))
    storage = FileCheckpointStorage(storage_path=str(path))
    before = len(REFUNDS)

    ui.section("Process 1: customer asks for a refund, workflow pauses for approval")
    workflow = build_workflow(checkpoint_storage=storage)
    message = "I was charged twice for ORD-1002, please refund $49."
    ui.user(message)
    pending = await _print_stream(workflow.run(message, stream=True))
    approval_pending = [e for e in pending if isinstance(e.data, Content) and e.data.type == "function_approval_request"]
    ui.note(f"pending requests: {len(pending)}, approval requests: {len(approval_pending)}")

    checkpoints = await storage.list_checkpoints(workflow_name="contoso_support")
    latest = sorted(checkpoints, key=lambda c: c.timestamp)[-1]
    ui.note(f"{len(checkpoints)} checkpoints saved under {path}. Latest: {latest.checkpoint_id}")
    ui.note("Process 1 exits. Nothing is held in memory.")

    ui.section("Process 2: an approver picks it up later")
    workflow2 = build_workflow(checkpoint_storage=storage)
    restored = await _print_stream(workflow2.run(checkpoint_id=latest.checkpoint_id, stream=True))
    responses: dict[str, object] = {}
    for req in restored:
        if isinstance(req.data, Content) and req.data.type == "function_approval_request":
            call = req.data.function_call
            ui.approval_request(call.name, call.parse_arguments() or {})
            approved = True
            if interactive:
                approved = ui.ask("  Approve? [y/N] ").strip().lower() in ("y", "yes")
            ui.approval_decision(approved)
            responses[req.request_id] = req.data.to_function_approval_response(approved=approved)
        elif isinstance(req.data, HandoffAgentUserRequest):
            responses[req.request_id] = HandoffAgentUserRequest.terminate()
    pending = await _print_stream(workflow2.run(responses=responses, stream=True))
    for req in pending:
        if isinstance(req.data, HandoffAgentUserRequest):
            await _print_stream(workflow2.run(responses={req.request_id: HandoffAgentUserRequest.terminate()}, stream=True))

    ui.section("Result")
    ui.note(f"refunds issued: {REFUNDS[before:]}")
    if storage_dir is None:
        shutil.rmtree(path, ignore_errors=True)
    return {"checkpoints": len(checkpoints), "approvals": len(approval_pending), "refunds": REFUNDS[before:]}
