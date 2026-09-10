"""A scripted, deterministic chat client for running the demo without any API key.

It plugs into the same layers real providers use (function invocation, chat middleware,
telemetry), so tools, approvals, middleware, handoffs, checkpoints and traces all behave
exactly as they would with a hosted model. Only the "thinking" is replaced by keyword rules.

Nothing here is needed when a real provider is configured; see ``config.make_client``.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from collections.abc import AsyncIterable, Awaitable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from agent_framework import (
    BaseChatClient,
    ChatMiddlewareLayer,
    ChatResponse,
    ChatResponseUpdate,
    Content,
    FunctionInvocationLayer,
    Message,
    ResponseStream,
    UsageDetails,
)
from agent_framework.observability import ChatTelemetryLayer

# --- routing vocabulary -----------------------------------------------------------------

DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "billing": ("refund", "charge", "charged", "invoice", "bill", "payment", "money back", "twice"),
    "orders": ("order", "track", "deliver", "shipping", "shipped", "where is", "package", "arrive", "eta"),
    "product": ("recommend", "product", "tent", "jacket", "boots", "backpack", "suggest", "gear", "stock",
                "inventory", "available", "in stock", "catalogue", "catalog"),
}

ORDER_RE = re.compile(r"\bORD-?\d{3,}\b", re.IGNORECASE)
MONEY_RE = re.compile(r"\$?\s?(\d+(?:\.\d{1,2})?)\s?(?:dollars|usd|\$)?", re.IGNORECASE)
SKU_RE = re.compile(r"\b[A-Z]{3}-\d{3}\b")

CAMPAIGN_BRIEF = (
    "Plan captured and executed. I checked the catalogue and stock; here is the campaign brief.\n"
    "1. Hero product: Trailhead 2-person tent ($249, 14 in stock).\n"
    "2. Bundle: Trailhead tent + Summit rain jacket + Daybreak 30L backpack, 'Weekend-ready' offer.\n"
    "3. Hold the Basecamp 4-person tent (out of stock) until restock; promote once inventory lands.\n"
    "Todo items are tracked in the harness todo list; file memory holds the stock snapshot for follow-ups."
)

PERSONA_FALLBACK: dict[str, str] = {
    "triage": "Thanks for contacting Contoso Retail. Is this about an order, a charge or refund, or product advice?",
    "orders": "I can help with order tracking. Which order number is it?",
    "billing": "I can help with invoices and refunds. Which order is this about, and what amount?",
    "product": "Happy to recommend gear. What are you planning, and do you have a budget in mind?",
    "concierge": "I can look up orders, invoices, products and stock. What do you need?",
    "assistant": "Understood. Let me work through that step by step.",
}


@dataclass
class ScriptContext:
    role: str
    messages: Sequence[Message]
    tools: dict[str, Any]
    instructions: str | None

    @property
    def last(self) -> Message:
        return self.messages[-1]

    @property
    def user_text(self) -> str:
        for m in reversed(self.messages):
            if m.role == "user" and m.text:
                return m.text
        return ""

    @property
    def transcript(self) -> str:
        return "\n".join(f"{m.role}: {m.text}" for m in self.messages if m.text)


class OfflineChatClient(FunctionInvocationLayer, ChatMiddlewareLayer, ChatTelemetryLayer, BaseChatClient):
    """Keyword-driven stand-in for a hosted model."""

    OTEL_PROVIDER_NAME = "offline"

    def __init__(self, *, role: str = "assistant", delay: float | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.role = role
        self.delay = float(os.getenv("OFFLINE_DELAY", "0.015")) if delay is None else delay
        self.model = "contoso-offline-1"
        self.seen_tools: list[str] = []

    # -- Agent Framework hook ---------------------------------------------------------

    def _inner_get_response(
        self,
        *,
        messages: Sequence[Message],
        options: Mapping[str, Any],
        stream: bool = False,
        **kwargs: Any,
    ) -> Awaitable[ChatResponse] | ResponseStream[ChatResponseUpdate, ChatResponse]:
        tools = {t.name: t for t in (options.get("tools") or []) if hasattr(t, "name")}
        for name in tools:
            if name not in self.seen_tools:
                self.seen_tools.append(name)
        ctx = ScriptContext(self.role, messages, tools, options.get("instructions"))
        contents = self.script(ctx)
        usage = Content.from_usage(
            UsageDetails(
                input_token_count=sum(len(m.text or "") // 4 for m in messages) + 40,
                output_token_count=sum(len(getattr(c, "text", "") or "") // 4 for c in contents) + 8,
            )
        )
        response_id = f"offline-{uuid.uuid4().hex[:8]}"
        message_id = f"msg-{uuid.uuid4().hex[:8]}"

        if stream:
            return self._build_response_stream(self._stream(contents, usage, response_id, message_id))

        async def _get() -> ChatResponse:
            return ChatResponse(
                messages=[Message("assistant", [*contents, usage], message_id=message_id)],
                response_id=response_id,
                model=self.model,
                finish_reason="tool_calls" if any(c.type == "function_call" for c in contents) else "stop",
            )

        return _get()

    async def _stream(
        self, contents: list[Content], usage: Content, response_id: str, message_id: str
    ) -> AsyncIterable[ChatResponseUpdate]:
        for content in contents:
            if content.type == "text":
                for word in re.split(r"(\s+)", content.text):
                    if not word:
                        continue
                    yield ChatResponseUpdate(
                        role="assistant",
                        contents=[Content.from_text(word)],
                        response_id=response_id,
                        message_id=message_id,
                        model=self.model,
                    )
                    if self.delay and word.strip():
                        await asyncio.sleep(self.delay)
            else:
                yield ChatResponseUpdate(
                    role="assistant", contents=[content], response_id=response_id, message_id=message_id, model=self.model
                )
        yield ChatResponseUpdate(
            role="assistant",
            contents=[usage],
            response_id=response_id,
            message_id=message_id,
            model=self.model,
            finish_reason="tool_calls" if any(c.type == "function_call" for c in contents) else "stop",
        )

    # -- the "brain" ------------------------------------------------------------------

    def script(self, ctx: ScriptContext) -> list[Content]:
        if ctx.last.role == "tool":
            return self._after_tools(ctx)

        text = ctx.user_text
        lowered = text.lower()
        domain = detect_domain(lowered)

        # Harness / planning agents: write a todo list first, then answer.
        todo_tool = next((n for n in ctx.tools if "todo" in n.lower() and ("add" in n.lower() or "write" in n.lower())), None)
        if todo_tool and not _already_called(ctx, todo_tool):
            return [Content.from_function_call(call_id=_cid(), name=todo_tool, arguments=_todo_args(ctx.tools[todo_tool], text))]

        # 1) A domain tool this agent owns.
        call = self._domain_tool_call(ctx, domain, lowered, text)
        if call is not None:
            return call

        # 2) Hand off to the specialist (or back to triage) if this agent cannot help.
        handoff = self._handoff(ctx, domain)
        if handoff is not None:
            return handoff

        # 3) Generic MCP / search tools, e.g. Microsoft Learn MCP.
        search_tool = next((n for n in ctx.tools if "search" in n.lower() and n not in ("search_products",)), None)
        if search_tool and not _already_called(ctx, search_tool):
            return [Content.from_function_call(call_id=_cid(), name=search_tool, arguments=_fill_args(ctx.tools[search_tool], text))]

        # 4) Persona answer.
        return [Content.from_text(self._persona_answer(ctx, text))]

    def _domain_tool_call(self, ctx: ScriptContext, domain: str | None, lowered: str, text: str) -> list[Content] | None:
        tools = ctx.tools
        order_id = _first(ORDER_RE, text, default="ORD-1001").upper().replace("ORD", "ORD-").replace("--", "-")

        def call(name: str, **args: Any) -> list[Content]:
            return [Content.from_function_call(call_id=_cid(), name=name, arguments=args)]

        if domain == "billing":
            if "issue_refund" in tools and "refund" in lowered:
                amount = float(_first(MONEY_RE, ORDER_RE.sub("", text), default="49"))
                reason = "customer reported a duplicate charge" if "twice" in lowered or "double" in lowered else "customer request"
                return call("issue_refund", order_id=order_id, amount=amount, reason=reason)
            if "get_invoice" in tools and not _already_called(ctx, "get_invoice"):
                return call("get_invoice", order_id=order_id)
        if domain == "orders" and "lookup_order" in tools:
            return call("lookup_order", order_id=order_id)
        if domain == "product":
            sku = _first(SKU_RE, text)
            if sku and "check_inventory" in tools:
                return call("check_inventory", sku=sku)
            if "search_products" in tools:
                query = next((k for k in ("tent", "jacket", "boots", "backpack", "camping", "apparel") if k in lowered), text)
                return call("search_products", query=query)
        return None

    def _handoff(self, ctx: ScriptContext, domain: str | None) -> list[Content] | None:
        handoffs = [n for n in ctx.tools if n.startswith("handoff_to_")]
        if not handoffs or domain is None or domain == ctx.role:
            return None
        target = f"handoff_to_{domain}"
        if target not in handoffs and "handoff_to_triage" in handoffs and ctx.role != "triage":
            target = "handoff_to_triage"
        if target not in handoffs:
            return None
        who = target.removeprefix("handoff_to_")
        line = (
            f"Sure, that's one for our {who} specialist. Connecting you now."
            if ctx.role == "triage"
            else f"That's outside what I handle, let me pass you back to {who} so they can route you."
        )
        return [Content.from_text(line), Content.from_function_call(call_id=_cid(), name=target, arguments={})]

    def _after_tools(self, ctx: ScriptContext) -> list[Content]:
        """Continue after tool results: either chain another tool call or answer."""
        text, next_call = self._after_tools_text(ctx)
        if next_call is not None:
            return [Content.from_function_call(call_id=_cid(), name=next_call[0], arguments=next_call[1])]
        return [Content.from_text(text)]

    def _after_tools_text(self, ctx: ScriptContext) -> tuple[str, tuple[str, dict[str, Any]] | None]:
        results: list[tuple[str, Any]] = []
        names: dict[str, str] = {}
        for m in ctx.messages:
            for c in m.contents:
                if c.type == "function_call":
                    names[c.call_id] = c.name
                elif c.type == "function_result":
                    results.append((names.get(c.call_id, "tool"), _parse(c.result)))
        name, data = results[-1]
        harness = any("todo" in n.lower() for n in ctx.tools)
        if isinstance(data, str) and "rejected" in data.lower():
            return "Understood, I have not issued the refund. Nothing has been credited or charged.", None
        if "todo" in name.lower():
            if "search_products" in ctx.tools and not _already_called(ctx, "search_products"):
                return "", ("search_products", {"query": "tent"})
            return CAMPAIGN_BRIEF, None
        if name == "search_products" and harness:
            return CAMPAIGN_BRIEF, None
        if name == "lookup_order" and isinstance(data, dict) and "order_id" in data:
            item = data["items"][0]["name"]
            if data["status"] == "shipped":
                return (
                    f"Order {data['order_id']} ({item}) has shipped with {data['carrier']}, tracking {data['tracking']}. "
                    f"It should arrive by {data['eta']}."
                ), None
            if data["status"] == "delivered":
                return f"Order {data['order_id']} ({item}) was delivered on {data['eta']}.", None
            return f"Order {data['order_id']} ({item}) is still being processed. Estimated dispatch so it arrives by {data['eta']}.", None
        if name == "get_invoice" and isinstance(data, dict) and "charges" in data:
            return f"Invoice for {data['order_id']}: one charge of ${data['total_charged']:.2f} to card {data['charges'][0]['card']}.", None
        if name == "issue_refund" and isinstance(data, dict):
            if "error" in data:
                return f"I couldn't process that refund: {data['error']}.", None
            return f"Done. A refund of ${data['amount']:.2f} for {data['order_id']} has been issued to the original payment method. It usually shows within 5 business days.", None
        if name == "search_products" and isinstance(data, list):
            lines = ", ".join(f"{p['name']} (${p['price']:.0f}, {p['stock']} in stock)" for p in data[:3])
            return f"Here's what I'd suggest: {lines}. Want me to check anything in more detail?", None
        if name == "check_inventory" and isinstance(data, dict):
            if data.get("stock", 0) > 0:
                return f"{data['name']} ({data['sku']}) is in stock: {data['stock']} available.", None
            return f"{data.get('name', data.get('sku'))} is currently out of stock.", None
        # Generic (e.g. MCP search results)
        if isinstance(data, dict) and isinstance(data.get("results"), list) and data["results"]:
            hit = data["results"][0]
            body = re.sub(r"[#*\[\]`>]+", "", str(hit.get("content", "")))
            body = re.sub(r"\(https?://[^)]+\)", "", body)
            body = " ".join(body.split())[:320]
            return f"From the Microsoft Learn page '{hit.get('title', 'untitled')}': {body}...", None
        snippet = json.dumps(data)[:400] if not isinstance(data, str) else data[:400]
        return f"Here is what I found from {name}: {snippet}", None

    def _persona_answer(self, ctx: ScriptContext, text: str) -> str:
        role = ctx.role
        topic = text.strip().rstrip(".") or "the request"
        if len(topic) > 60:
            topic = topic[:57].rstrip() + "..."
        if role == "researcher":
            return (
                f"Research on '{topic}':\n"
                "- Demand: urban commuters and weekend hikers are the fastest growing outdoor segments.\n"
                "- Opportunity: bundles (tent + jacket + pack) lift average order value by ~18% in comparable retailers.\n"
                "- Risk: seasonal stock-outs on hero SKUs erode campaign ROI."
            )
        if role == "marketer":
            return (
                f"Marketing angle for '{topic}':\n"
                "Value proposition: 'Trail-ready gear, weekend-ready prices.'\n"
                "1. Bundle-and-save launch offer.\n2. Creator hikes with UGC.\n3. Loyalty early access for existing customers."
            )
        if role == "legal":
            return (
                f"Compliance review for '{topic}':\n"
                "- Substantiate any 'waterproof' or 'lightest' claims with test data.\n"
                "- Promotions need clear end dates and stock-availability disclaimers.\n"
                "- Loyalty data use must match the privacy notice."
            )
        if role == "summarizer":
            return (
                "Launch brief: position the spring range as trail-ready gear at weekend-ready prices, led by a "
                "bundle-and-save offer on the Trailhead tent, Summit jacket and Daybreak pack. Amplify with creator "
                "hikes and loyalty early access. Before launch, substantiate product claims, add promotion end dates "
                "and stock disclaimers, and confirm loyalty data use matches the privacy notice. Watch hero-SKU "
                "stock levels weekly."
            )
        if role == "assistant":
            return PERSONA_FALLBACK["assistant"] + f" Here is my answer to: {topic}."
        return PERSONA_FALLBACK.get(role, f"Here's my take on: {topic}.")


# --- helpers ------------------------------------------------------------------------


def detect_domain(lowered: str) -> str | None:
    scores = {d: sum(1 for k in kws if k in lowered) for d, kws in DOMAIN_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else None


def _cid() -> str:
    return f"call_{uuid.uuid4().hex[:10]}"


def _first(pattern: re.Pattern[str], text: str, default: str = "") -> str:
    m = pattern.search(text)
    if not m:
        return default
    return m.group(1) if m.groups() else m.group(0)


def _parse(result: Any) -> Any:
    if isinstance(result, list) and result and hasattr(result[0], "text"):
        result = result[0].text
    if isinstance(result, str):
        try:
            return json.loads(result)
        except ValueError:
            pass
        try:
            # Some tools return JSON followed by extra text or several concatenated objects.
            value, _ = json.JSONDecoder().raw_decode(result.lstrip())
            return value
        except ValueError:
            return result
    return result


def _already_called(ctx: ScriptContext, tool_name: str) -> bool:
    return any(c.type == "function_call" and c.name == tool_name for m in ctx.messages for c in m.contents)


def _fill_args(tool: Any, text: str) -> dict[str, Any]:
    props = (tool.parameters() or {}).get("properties", {}) if callable(getattr(tool, "parameters", None)) else {}
    args: dict[str, Any] = {}
    for name, spec in props.items():
        typ = spec.get("type", "string")
        if typ == "string":
            args[name] = text
        elif typ in ("integer", "number"):
            args[name] = 5
        elif typ == "boolean":
            args[name] = True
        elif typ == "array":
            args[name] = [text]
    return args


def _todo_args(tool: Any, text: str) -> dict[str, Any]:
    items = [
        ("Check catalogue and stock for tents, jackets and packs", "Use search_products / check_inventory"),
        ("Pick a hero product and a bundle", "Prefer in-stock items"),
        ("Draft the campaign brief", "Short, with three angles"),
    ]
    if tool.name == "todos_add":
        return {"todos": [{"title": t, "description": d} for t, d in items]}
    props = (tool.parameters() or {}).get("properties", {}) if callable(getattr(tool, "parameters", None)) else {}
    items = [
        "Check catalogue and stock for hiking gear",
        "Pick hero product and bundle",
        "Draft campaign brief",
    ]
    args: dict[str, Any] = {}
    for name, spec in props.items():
        typ = spec.get("type")
        if typ == "array":
            item_schema = spec.get("items", {})
            if item_schema.get("type") == "object":
                item_props = item_schema.get("properties", {})
                objs = []
                for i, title in enumerate(items):
                    obj: dict[str, Any] = {}
                    for pname, pspec in item_props.items():
                        if pspec.get("type") == "string":
                            enum = pspec.get("enum")
                            if enum:
                                obj[pname] = enum[0]
                            elif pname in ("id",):
                                obj[pname] = str(i + 1)
                            else:
                                obj[pname] = title
                        elif pspec.get("type") == "integer":
                            obj[pname] = i + 1
                        elif pspec.get("type") == "boolean":
                            obj[pname] = False
                    objs.append(obj)
                args[name] = objs
            else:
                args[name] = items
        elif typ == "string":
            args[name] = text
    return args
