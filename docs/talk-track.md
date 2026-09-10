# Talk track: Microsoft Agent Framework in 20 minutes

Audience: technical decision makers and lead engineers. Goal: show that agents are ready for real business processes, not just chat.

Before the meeting: `pip install -e .`, run `python -m contoso_agents all` once so the first run is warm, and decide whether to demo offline (safe) or on a real model (more impressive, riskier).

## 0. Framing (2 min)

"Microsoft Agent Framework is the successor to Semantic Kernel and AutoGen, GA since April 2026, same API in .NET and Python. Two ideas: an **agent** for open-ended tasks, and a **workflow** when the process has fixed steps and needs control. Everything you see today runs with no API key; the same code runs on Foundry or Azure OpenAI by changing one variable."

## 1. One agent, real tools (3 min)

```
python -m contoso_agents agent
```

Point out: the yellow lines are the agent choosing a tool and the tool answering. Three turns, one session, the third turn builds on the second. "Tools are plain Python functions with a decorator. No prompt engineering to get JSON out."

## 2. Human in the loop (3 min)

```
python -m contoso_agents approval -i
```

Type `y` for the first refund and `n` for the second. Point out: the tool is marked as requiring approval, the agent stops and asks, and the declined refund never runs. "This is the difference between a chatbot and something Finance will sign off."

## 3. Policy as code (2 min)

```
python -m contoso_agents guardrails
```

Point out: the card number never reached the model (model calls stay at 2), and every tool call is logged with arguments and timing. "Middleware is where security, compliance and cost controls live. Same pattern for Purview or your own DLP."

## 4. Specialists that hand off (4 min)

```
python -m contoso_agents handoff
```

Point out the magenta handoff lines: triage to orders, orders back to triage, triage to billing, and the approval prompt inside the workflow. "Each specialist has its own tools and instructions. The customer sees one conversation. The refund still needs a human."

If time: run it with `-i` and let the customer type.

## 5. Parallel experts (2 min)

```
python -m contoso_agents concurrent
```

Point out: three agents run at the same time, and a fourth writes the brief. "Fan-out, fan-in. Use it for reviews, ensembles, second opinions."

## 6. Durable processes (2 min)

```
python -m contoso_agents checkpoint
```

Point out: process 1 exits with the approval outstanding; process 2 restores from a JSON checkpoint and finishes. "Approvals that take a day, not a second. Nothing is held in memory."

## 7. The Harness (1 min)

```
python -m contoso_agents harness
```

Point out the injected tools: todos, modes, file memory. "This is Microsoft's opinionated agent for long-running work. You bring the model and your tools; planning, memory, compaction, approvals and telemetry come in the box."

## 8. Observability (1 min)

```
python -m contoso_agents trace
```

Point out the span tree with token counts. "Standard OpenTelemetry, GenAI semantic conventions. Send it to Application Insights, Aspire Dashboard, Jaeger or Langfuse."

## 9. Optional closers

- `python -m contoso_agents mcp` (network): the agent uses the public Microsoft Learn MCP server. "Any MCP server becomes a tool."
- `python -m contoso_agents devui`: browse the agents and workflows in a web UI, then call one through the OpenAI-compatible API.
- On a real model: `python -m contoso_agents magentic -i` and approve the manager's plan live.

## Questions to expect

- **.NET?** Same concepts and API shape in `Microsoft.Agents.AI`. Go is in public preview.
- **Hosting?** Foundry Hosted Agents (scale to zero, per-session isolation, Application Insights) or any container; Azure Functions and Durable Task integrations ship as packages.
- **Migration from Semantic Kernel or AutoGen?** Official migration guides; Agent Framework is built by the same teams.
- **Model lock-in?** Foundry, Azure OpenAI, OpenAI, Anthropic, Gemini, Mistral, Bedrock, Ollama behind one `Agent`.
- **Security of MCP?** Local and hosted MCP tools, per-request headers, trace propagation, approval gates via the same middleware.
