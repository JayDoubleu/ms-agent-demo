"""Contoso Retail back-office tools.

Plain Python functions decorated with ``@tool`` become function tools the model can call.
``issue_refund`` is marked ``approval_mode="always_require"`` so a human must approve it
before it runs (human-in-the-loop), which the approval, handoff and checkpoint scenarios
all rely on.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Annotated

from agent_framework import tool
from pydantic import Field

# --- fake back-office data -----------------------------------------------------------

ORDERS: dict[str, dict] = {
    "ORD-1001": {
        "order_id": "ORD-1001",
        "customer": "Alex Rivera",
        "status": "shipped",
        "carrier": "Contoso Express",
        "tracking": "CX-7781-2231",
        "eta": (date.today() + timedelta(days=2)).isoformat(),
        "items": [{"sku": "TNT-200", "name": "Trailhead 2-person tent", "qty": 1}],
        "total": 249.00,
    },
    "ORD-1002": {
        "order_id": "ORD-1002",
        "customer": "Alex Rivera",
        "status": "delivered",
        "carrier": "Contoso Express",
        "tracking": "CX-7781-1188",
        "eta": (date.today() - timedelta(days=3)).isoformat(),
        "items": [{"sku": "JKT-410", "name": "Summit rain jacket", "qty": 1}],
        "total": 49.00,
    },
    "ORD-1003": {
        "order_id": "ORD-1003",
        "customer": "Sam Chen",
        "status": "processing",
        "carrier": None,
        "tracking": None,
        "eta": (date.today() + timedelta(days=6)).isoformat(),
        "items": [{"sku": "BTS-118", "name": "Ridge hiking boots", "qty": 2}],
        "total": 318.00,
    },
}

PRODUCTS: list[dict] = [
    {"sku": "TNT-200", "name": "Trailhead 2-person tent", "category": "camping", "price": 249.00, "stock": 14},
    {"sku": "TNT-300", "name": "Basecamp 4-person tent", "category": "camping", "price": 399.00, "stock": 0},
    {"sku": "JKT-410", "name": "Summit rain jacket", "category": "apparel", "price": 49.00, "stock": 120},
    {"sku": "JKT-420", "name": "Alpine insulated jacket", "category": "apparel", "price": 189.00, "stock": 8},
    {"sku": "BTS-118", "name": "Ridge hiking boots", "category": "footwear", "price": 159.00, "stock": 33},
    {"sku": "BAG-050", "name": "Daybreak 30L backpack", "category": "packs", "price": 89.00, "stock": 51},
]

REFUNDS: list[dict] = []
"""Refunds issued during this process. Inspected by the tests."""


# --- tools --------------------------------------------------------------------------


@tool
def lookup_order(
    order_id: Annotated[str, Field(description="Order number, e.g. ORD-1001")],
) -> str:
    """Look up an order: status, carrier, tracking number, ETA, items and total."""
    order = ORDERS.get(order_id.upper())
    if not order:
        return json.dumps({"error": f"Order {order_id} not found"})
    return json.dumps(order)


@tool
def search_products(
    query: Annotated[str, Field(description="Free text search, e.g. 'tent' or 'rain jacket'")],
) -> str:
    """Search the Contoso catalogue by name or category."""
    q = query.lower()
    hits = [p for p in PRODUCTS if q in p["name"].lower() or q in p["category"]]
    if not hits:
        words = [w for w in q.replace(",", " ").split() if len(w) > 3]
        hits = [p for p in PRODUCTS if any(w in p["name"].lower() or w in p["category"] for w in words)]
    return json.dumps(hits or PRODUCTS[:3])


@tool
def check_inventory(
    sku: Annotated[str, Field(description="Product SKU, e.g. TNT-200")],
) -> str:
    """Return live stock level for a SKU."""
    for p in PRODUCTS:
        if p["sku"] == sku.upper():
            return json.dumps({"sku": p["sku"], "name": p["name"], "stock": p["stock"]})
    return json.dumps({"error": f"SKU {sku} not found"})


@tool
def get_invoice(
    order_id: Annotated[str, Field(description="Order number, e.g. ORD-1002")],
) -> str:
    """Return the invoice (charges) for an order."""
    order = ORDERS.get(order_id.upper())
    if not order:
        return json.dumps({"error": f"Order {order_id} not found"})
    return json.dumps(
        {
            "order_id": order["order_id"],
            "charges": [{"date": order["eta"], "amount": order["total"], "card": "**** 4242"}],
            "total_charged": order["total"],
        }
    )


@tool(approval_mode="always_require")
def issue_refund(
    order_id: Annotated[str, Field(description="Order number to refund")],
    amount: Annotated[float, Field(description="Refund amount in USD")],
    reason: Annotated[str, Field(description="Short reason for the refund")],
) -> str:
    """Issue a refund to the customer's original payment method. Requires human approval."""
    order = ORDERS.get(order_id.upper())
    if not order:
        return json.dumps({"error": f"Order {order_id} not found"})
    if amount > order["total"]:
        return json.dumps({"error": f"Refund {amount} exceeds order total {order['total']}"})
    record = {"order_id": order["order_id"], "amount": amount, "reason": reason, "status": "refunded"}
    REFUNDS.append(record)
    return json.dumps(record)


ALL_TOOLS = [lookup_order, search_products, check_inventory, get_invoice, issue_refund]
