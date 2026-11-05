"""Operators decide what the business does each day.

``RuleBasedOperator`` is a fixed policy that runs offline and needs no API key.
``ClaudeOperator`` gives the day to a Claude model through the Messages API using tool use.
"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

from .prompts import OPERATOR_BRIEFING
from .session import Session
from .tools import TOOL_SPECS
from .world import World

DEFAULT_MODEL = "claude-opus-5-5"

NUDGE = "Today's books are not closed yet. When the day's work is finished, call end_day."


class Operator(Protocol):
    name: str

    def run_day(self, session: Session) -> None:
        """Do the day's work through ``session.call``. The runner closes the day if this returns without doing so."""
        ...


def morning_message(world: World) -> str:
    today = world.date
    return (
        f"Good morning. It is {today:%A, %d %B %Y}, day {world.day} of trading.\n\n"
        f"Status:\n{json.dumps(world.status(), indent=2)}\n\n"
        f"Your notes from earlier days:\n{world.notes or '(none yet)'}\n\n"
        "Get today's work done, then call end_day."
    )


class RuleBasedOperator:
    """Offline baseline. When stock runs low it orders from the cheapest supplier that accepts the order size.

    It never changes prices. Useful for trying the simulator without an API key, and as a sanity check
    that the economics can be run profitably.
    """

    name = "rules"

    def __init__(self, reorder_point: int = 10, restock_units: int = 30):
        self.reorder_point = reorder_point
        self.restock_units = restock_units

    def run_day(self, session: Session) -> None:
        products, _ = session.call("list_products", {})
        suppliers, _ = session.call("list_suppliers", {})
        orders, _ = session.call("list_orders", {})
        in_transit = {order["sku"] for order in orders if order["status"] == "in transit"}

        for product in products:
            sku = product["sku"]
            if product["stock"] > self.reorder_point or sku in in_transit:
                continue
            offers = [
                (supplier["supplier_id"], offer)
                for supplier in suppliers
                for offer in supplier["offers"]
                if offer["sku"] == sku and offer["min_order_qty"] <= self.restock_units
            ]
            if not offers:
                continue
            supplier_id, _ = min(offers, key=lambda pair: pair[1]["unit_cost_cents"])
            session.call(
                "place_order",
                {"supplier_id": supplier_id, "sku": sku, "quantity": self.restock_units},
            )

        session.call("end_day", {})


def _block_to_param(block: Any) -> dict:
    """Turn a response content block back into a request param so it can be sent in the next turn."""
    if hasattr(block, "model_dump"):
        return block.model_dump(mode="json", exclude_none=True)
    if block.type == "text":
        return {"type": "text", "text": block.text}
    if block.type == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    raise ValueError(f"unsupported content block type: {block.type}")


def _usage(response: Any) -> dict | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return {
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
    }


class ClaudeOperator:
    """Runs each day as one conversation with a Claude model that has the business tools.

    Each day starts with a fresh conversation. Only the operator's notes carry over, which keeps context
    short and makes the memory constraint explicit.
    """

    name = "claude"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        client: Any = None,
        max_turns_per_day: int = 40,
        max_tokens: int = 2048,
    ):
        self.model = model
        self.max_turns_per_day = max_turns_per_day
        self.max_tokens = max_tokens
        if client is None:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise RuntimeError("Set ANTHROPIC_API_KEY to use the claude operator.")
            try:
                import anthropic
            except ImportError as exc:
                raise RuntimeError("Install the extra: pip install 'business-sim[claude]'") from exc
            client = anthropic.Anthropic()
        self.client = client

    def run_day(self, session: Session) -> None:
        day = session.world.day
        briefing = morning_message(session.world)
        session.log.event("briefing", day=day, text=briefing)
        messages: list[dict] = [{"role": "user", "content": briefing}]

        for _ in range(self.max_turns_per_day):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=OPERATOR_BRIEFING,
                tools=TOOL_SPECS,
                messages=messages,
            )
            session.log.event(
                "model_turn",
                day=day,
                stop_reason=getattr(response, "stop_reason", None),
                usage=_usage(response),
            )
            for block in response.content:
                if block.type == "text" and block.text.strip():
                    session.log.event("assistant_text", day=day, text=block.text)
            messages.append({"role": "assistant", "content": [_block_to_param(b) for b in response.content]})

            tool_uses = [block for block in response.content if block.type == "tool_use"]
            if tool_uses:
                results = []
                for block in tool_uses:
                    result, is_error = session.call(block.name, block.input)
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                            "is_error": is_error,
                        }
                    )
                messages.append({"role": "user", "content": results})

            if session.closed:
                return
            if not tool_uses:
                messages.append({"role": "user", "content": NUDGE})
        # Turn budget spent: the simulation closes the day.
