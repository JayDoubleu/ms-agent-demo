# Contoso Agents: Microsoft Agent Framework showcase

A runnable, customer-facing demo of **Microsoft Agent Framework 1.x**, the production successor to Semantic Kernel and AutoGen. It is built as a small Contoso Retail support and merchandising system and walks through the framework's headline capabilities one scenario at a time.

Everything runs **offline with no API keys** against a scripted model, so the demo never depends on Wi-Fi or quota in the room. Flip one environment variable and the same code runs on Azure OpenAI, Microsoft Foundry, OpenAI, Anthropic or Ollama.

Built and verified against `agent-framework` **1.18.0** (released 10 September 2026).

## What the audience sees

| # | Scenario | Command | Framework feature |
|---|----------|---------|-------------------|
| 1 | Concierge answers order, stock and product questions across turns | `agent` | `Agent`, `@tool`, `AgentSession`, streaming |
| 2 | Refund needs a human yes/no before the tool runs | `approval` | `@tool(approval_mode="always_require")`, `user_input_requests` |
| 3 | Card number is blocked before the model sees it; every tool call is audited | `guardrails` | agent, function and chat middleware |
| 4 | Triage routes to orders, billing and product specialists; refund inside the workflow still needs approval | `handoff` | `HandoffBuilder`, `add_handoff`, `request_info` events |
| 5 | Researcher, marketer and legal review a launch in parallel; a summarizer aggregates | `concurrent` | `ConcurrentBuilder`, intermediate outputs, custom aggregator |
| 6 | Batteries-included agent plans with todos, modes and file memory | `harness` | `create_harness_agent` (new in 2026) |
| 7 | Workflow pauses for approval, process exits, another process resumes it | `checkpoint` | `FileCheckpointStorage`, `run(checkpoint_id=...)` |
| 8 | Span tree for agent, model and tool calls | `trace` | OpenTelemetry GenAI semantic conventions |
| 9 | Agent uses the public Microsoft Learn MCP server as tools | `mcp` | `MCPStreamableHTTPTool` (needs network) |
| 10 | Manager plans, delegates, tracks progress and synthesizes | `magentic` | `MagenticBuilder`, plan review (needs a real model) |
| UI | Web app to chat with any agent or workflow, plus an OpenAI-compatible API | `devui` | DevUI |

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

python -m contoso_agents list        # see the scenarios
python -m contoso_agents agent       # run one
python -m contoso_agents all         # run everything that works with the current provider
python -m contoso_agents handoff -i  # interactive: you type the customer's messages
python -m contoso_agents devui       # web UI on http://127.0.0.1:8080
pytest -q                            # 11 end-to-end tests, offline, under a second
```

Python 3.10 or newer. First install pulls the full `agent-framework` bundle and takes a couple of minutes.

## Switching to a real model

Copy `.env.example` to `.env` and fill in one provider. The demo auto-detects it; set `AGENT_PROVIDER` to force a choice.

| Provider | Variables | Auth |
|----------|-----------|------|
| Azure OpenAI | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_CHAT_MODEL` | `AZURE_OPENAI_API_KEY` or `az login` |
| Microsoft Foundry | `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL` | `az login` |
| OpenAI | `OPENAI_API_KEY`, `OPENAI_CHAT_MODEL` | key |
| Anthropic | `ANTHROPIC_API_KEY`, `ANTHROPIC_CHAT_MODEL` | key |
| Ollama | `OLLAMA_HOST`, `OLLAMA_CHAT_MODEL` | none |

With a real model the scripted personas disappear and the agents reason for themselves. Scenario 10 (Magentic) only runs with a real model.

## How it is put together

```
contoso_agents/
  config.py            provider detection and make_client(role)
  offline_client.py    scripted chat client built on the same layers real providers use
  tools.py             Contoso back-office tools (@tool), refund requires approval
  middleware.py        PII guard, tool audit, model call counter
  agents.py            triage / orders / billing / product / launch-review panel
  runtime.py           streaming turn runner that resolves approval requests
  scenarios/           one module per scenario, each with TITLE and async run()
  devui_app.py         registers agents and workflows with DevUI
  __main__.py          CLI
tests/                 end-to-end offline tests
docs/talk-track.md     20-minute customer walkthrough
```

The offline client subclasses `BaseChatClient` and mixes in the framework's `FunctionInvocationLayer`, `ChatMiddlewareLayer` and `ChatTelemetryLayer`, so tools, approvals, middleware, handoffs, checkpoints and traces are the real framework code paths. Only the model's "thinking" is replaced by keyword rules.

## Why this matters to a customer

- **One framework, both stacks.** The same concepts and API shape ship for .NET and Python, with Go in preview.
- **Agents when the task is open-ended, workflows when the process is fixed.** Graph-based workflows give explicit control, checkpoints and human-in-the-loop for long-running business processes.
- **Enterprise plumbing is built in.** Middleware for policy, OpenTelemetry for observability, Purview and Application Insights integrations, tool approval by default in the Harness.
- **Open protocols.** MCP for tools, A2A for cross-framework agents, an OpenAI-compatible surface through DevUI and Foundry hosting.
- **Provider choice.** Foundry, Azure OpenAI, OpenAI, Anthropic, Ollama and more behind one `Agent`.

## References

- Overview: https://learn.microsoft.com/agent-framework/overview/agent-framework-overview
- Harness agent: https://learn.microsoft.com/agent-framework/concepts/harness
- Handoff orchestration: https://learn.microsoft.com/agent-framework/workflows/orchestrations/handoff
- Magentic orchestration: https://learn.microsoft.com/agent-framework/workflows/orchestrations/magentic
- Observability: https://learn.microsoft.com/agent-framework/agents/observability
- DevUI: https://learn.microsoft.com/agent-framework/integrations/by-component/ui/devui/
- 2026 API changes (for anyone migrating older samples): https://learn.microsoft.com/agent-framework/support/upgrade/python-2026-significant-changes
- BUILD 2026 announcements (Harness, Hosted Agents, CodeAct): https://devblogs.microsoft.com/agent-framework/microsoft-agent-framework-at-build-2026-announce/
- Source: https://github.com/microsoft/agent-framework
