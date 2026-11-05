"""Tools the operator can call, and the code that runs them.

Every tool takes plain JSON arguments and returns a JSON-serialisable result.
Rule violations come back as ``{"error": ...}`` with ``is_error`` set, so the
operator can recover the same way it would from a real system.
"""

from __future__ import annotations

from typing import Any

from .world import MAX_NOTES_CHARS, MAX_PRICE_CENTS, MIN_PRICE_CENTS, SimError, World

# Tool name -> World method name.
_METHOD_FOR_TOOL = {
    "get_status": "status",
    "list_products": "list_products",
    "set_price": "set_price",
    "list_suppliers": "list_suppliers",
    "place_order": "place_order",
    "list_orders": "list_orders",
    "sales_report": "sales_report",
    "get_ledger": "get_ledger",
    "read_inbox": "read_inbox",
    "send_email": "send_email",
    "read_notes": "read_notes",
    "write_notes": "write_notes",
    "end_day": "close_day",
}


def _spec(name: str, description: str, properties: dict | None = None, required: tuple = ()) -> dict:
    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": properties or {},
            "required": list(required),
            "additionalProperties": False,
        },
    }


TOOL_SPECS: list[dict] = [
    _spec("get_status", "Today's date, cash balance, unread message count and orders in transit."),
    _spec("list_products", "The products you sell, with current selling price and stock on hand."),
    _spec(
        "set_price",
        "Change the selling price of one product. The new price applies to customers straight away.",
        {
            "sku": {"type": "string", "description": "Product SKU, for example MUG-01."},
            "price_cents": {
                "type": "integer",
                "minimum": MIN_PRICE_CENTS,
                "maximum": MAX_PRICE_CENTS,
                "description": "New price in cents, for example 1250 for $12.50.",
            },
        },
        required=("sku", "price_cents"),
    ),
    _spec(
        "list_suppliers",
        "Suppliers you can buy from, with their unit costs, minimum order quantities and lead times.",
    ),
    _spec(
        "place_order",
        "Buy stock from a supplier. The invoice is paid immediately and the goods arrive after the "
        "supplier's lead time.",
        {
            "supplier_id": {"type": "string", "description": "Supplier ID, for example RCS."},
            "sku": {"type": "string", "description": "Product SKU to buy."},
            "quantity": {"type": "integer", "minimum": 1, "description": "Units to buy."},
        },
        required=("supplier_id", "sku", "quantity"),
    ),
    _spec("list_orders", "Purchase orders you have placed, newest first, with their status."),
    _spec(
        "sales_report",
        "Units sold, revenue and card fees per product for recently completed days.",
        {
            "last_days": {
                "type": "integer",
                "minimum": 1,
                "maximum": 60,
                "description": "How many completed days to cover (default 7).",
            },
        },
    ),
    _spec(
        "get_ledger",
        "The most recent bank account entries, newest first.",
        {"limit": {"type": "integer", "minimum": 1, "maximum": 200, "description": "Entries to return (default 20)."}},
    ),
    _spec(
        "read_inbox",
        "Read your email, newest first (up to 50 messages). Messages returned are marked as read.",
        {"unread_only": {"type": "boolean", "description": "Only return unread messages."}},
    ),
    _spec(
        "send_email",
        "Send an email to a supplier, or to anyone who has written to you.",
        {
            "to": {"type": "string", "description": "Email address of the recipient."},
            "subject": {"type": "string"},
            "body": {"type": "string", "maxLength": 5000},
        },
        required=("to", "subject", "body"),
    ),
    _spec(
        "read_notes",
        "Read your notes. Notes are the only thing that carries over from one day to the next.",
    ),
    _spec(
        "write_notes",
        "Replace your notes. Anything you will need tomorrow has to be written here.",
        {"text": {"type": "string", "maxLength": MAX_NOTES_CHARS}},
        required=("text",),
    ),
    _spec(
        "end_day",
        "Close today's books: deliveries arrive, customers buy, and overheads are paid. Call this once "
        "today's work is finished. Trading tools are unavailable afterwards.",
    ),
]

_SPECS_BY_NAME = {spec["name"]: spec for spec in TOOL_SPECS}


def _check_value(key: str, prop: dict, value: Any) -> None:
    kind = prop["type"]
    if kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise SimError(f"{key} must be an integer")
        if "minimum" in prop and value < prop["minimum"]:
            raise SimError(f"{key} must be at least {prop['minimum']}")
        if "maximum" in prop and value > prop["maximum"]:
            raise SimError(f"{key} must be at most {prop['maximum']}")
    elif kind == "string":
        if not isinstance(value, str):
            raise SimError(f"{key} must be a string")
        if "maxLength" in prop and len(value) > prop["maxLength"]:
            raise SimError(f"{key} is too long (maximum {prop['maxLength']} characters)")
    elif kind == "boolean":
        if not isinstance(value, bool):
            raise SimError(f"{key} must be true or false")


def _check_args(schema: dict, args: Any) -> None:
    if not isinstance(args, dict):
        raise SimError("arguments must be a JSON object")
    properties = schema["properties"]
    for key in schema["required"]:
        if key not in args:
            raise SimError(f"missing required argument {key!r}")
    for key, value in args.items():
        if key not in properties:
            raise SimError(f"unexpected argument {key!r}")
        _check_value(key, properties[key], value)


def execute(world: World, name: str, args: Any) -> tuple[Any, bool]:
    """Run one tool call. Returns ``(result, is_error)``."""
    spec = _SPECS_BY_NAME.get(name)
    if spec is None:
        return {"error": f"unknown tool {name!r}"}, True
    try:
        _check_args(spec["input_schema"], args)
        result = getattr(world, _METHOD_FOR_TOOL[name])(**args)
    except SimError as exc:
        return {"error": str(exc)}, True
    return result, False
