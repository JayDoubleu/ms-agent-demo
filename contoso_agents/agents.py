"""Agent definitions for Contoso Retail.

Every agent is a plain ``Agent`` built from ``make_client(role)``, so the same definitions
run against the offline scripted model or any real provider. ``id`` is set explicitly and
equals ``name`` so handoff tools are stable (``handoff_to_billing``) and checkpoints can be
rehydrated.
"""

from __future__ import annotations

from agent_framework import Agent

from .config import make_client
from .middleware import PiiGuardMiddleware, audit_tool_calls, count_model_calls
from .tools import check_inventory, get_invoice, issue_refund, lookup_order, search_products

STYLE = "Be concise and friendly. Use plain language. Never invent order data: always use tools."

# Handoff workflows short-circuit the handoff tool call locally, so every participant must
# persist history after each service call to stay consistent with the model service.
HANDOFF_AGENT = {"require_per_service_call_history_persistence": True}


def concierge_agent() -> Agent:
    """One agent with every tool. Used by the single-agent, observability and DevUI scenarios."""
    return Agent(
        client=make_client("concierge"),
        id="concierge",
        name="concierge",
        description="Contoso Retail concierge that can look up orders, invoices, products and stock.",
        instructions=f"You are the Contoso Retail concierge. {STYLE}",
        tools=[lookup_order, get_invoice, search_products, check_inventory],
        middleware=[audit_tool_calls],
    )


def guarded_billing_agent() -> Agent:
    """Billing agent with a PII guard, tool audit and model call counter."""
    return Agent(
        client=make_client("billing"),
        id="billing",
        name="billing",
        description="Handles invoices and refunds.",
        instructions=f"You are a Contoso billing specialist. You can read invoices and issue refunds. {STYLE}",
        tools=[get_invoice, issue_refund],
        middleware=[PiiGuardMiddleware(), audit_tool_calls, count_model_calls],
    )


def triage_agent() -> Agent:
    return Agent(
        client=make_client("triage"),
        id="triage",
        name="triage",
        description="Front-line support. Greets the customer and routes to the right specialist.",
        instructions=(
            "You are Contoso Retail front-line support. Work out whether the customer needs "
            "the orders specialist (tracking, delivery), the billing specialist (charges, refunds) "
            "or the product specialist (recommendations, stock), then hand off. "
            "If the request is unclear, ask one short clarifying question. " + STYLE
        ),
        **HANDOFF_AGENT,
    )


def orders_agent() -> Agent:
    return Agent(
        client=make_client("orders"),
        id="orders",
        name="orders",
        description="Order tracking and delivery specialist.",
        instructions=(
            "You are the Contoso orders specialist. Look up orders and explain status, tracking and ETA. "
            "If the customer asks about charges, refunds or products, hand back to triage. " + STYLE
        ),
        tools=[lookup_order],
        middleware=[audit_tool_calls],
        **HANDOFF_AGENT,
    )


def billing_agent() -> Agent:
    return Agent(
        client=make_client("billing"),
        id="billing",
        name="billing",
        description="Invoices and refunds specialist.",
        instructions=(
            "You are the Contoso billing specialist. Check invoices and issue refunds when justified. "
            "Refunds require approval; explain the outcome. If the customer asks about delivery or "
            "products, hand back to triage. " + STYLE
        ),
        tools=[get_invoice, issue_refund],
        middleware=[audit_tool_calls],
        **HANDOFF_AGENT,
    )


def product_agent() -> Agent:
    return Agent(
        client=make_client("product"),
        id="product",
        name="product",
        description="Product advice and stock specialist.",
        instructions=(
            "You are the Contoso product specialist. Recommend products from the catalogue and check stock. "
            "If the customer asks about an existing order or a charge, hand back to triage. " + STYLE
        ),
        tools=[search_products, check_inventory],
        middleware=[audit_tool_calls],
        **HANDOFF_AGENT,
    )


# --- launch review panel (concurrent orchestration) ---------------------------------


def researcher_agent() -> Agent:
    return Agent(
        client=make_client("researcher"),
        id="researcher",
        name="researcher",
        description="Market researcher.",
        instructions="You are a market researcher. Give three concise, factual insights, opportunities and risks.",
    )


def marketer_agent() -> Agent:
    return Agent(
        client=make_client("marketer"),
        id="marketer",
        name="marketer",
        description="Marketing strategist.",
        instructions="You are a marketing strategist. Propose a value proposition and three campaign angles.",
    )


def legal_agent() -> Agent:
    return Agent(
        client=make_client("legal"),
        id="legal",
        name="legal",
        description="Legal and compliance reviewer.",
        instructions="You are a cautious legal and compliance reviewer. List constraints, disclaimers and policy concerns.",
    )


def summarizer_agent() -> Agent:
    return Agent(
        client=make_client("summarizer"),
        id="summarizer",
        name="summarizer",
        description="Consolidates expert input into one brief.",
        instructions=(
            "Consolidate the expert sections you are given into one launch brief with clear takeaways, "
            "under 150 words."
        ),
    )
