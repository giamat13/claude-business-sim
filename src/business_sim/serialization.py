"""Rebuild a World from the plain dict produced by ``dataclasses.asdict``."""

from __future__ import annotations

import datetime as dt

from .world import LedgerEntry, Message, Product, PurchaseOrder, Supplier, SupplierOffer, World


def world_from_dict(data: dict) -> World:
    return World(
        start_date=dt.date.fromisoformat(data["start_date"]),
        seed=data["seed"],
        opening_cash_cents=data["opening_cash_cents"],
        cash_cents=data["cash_cents"],
        products={sku: Product(**fields) for sku, fields in data["products"].items()},
        suppliers={
            supplier_id: Supplier(
                **{**fields, "offers": [SupplierOffer(**offer) for offer in fields["offers"]]}
            )
            for supplier_id, fields in data["suppliers"].items()
        },
        day=data["day"],
        orders=[PurchaseOrder(**fields) for fields in data["orders"]],
        ledger=[LedgerEntry(**fields) for fields in data["ledger"]],
        inbox=[Message(**fields) for fields in data["inbox"]],
        outbox=data["outbox"],
        notes=data["notes"],
        insolvent=data["insolvent"],
        next_id=data["next_id"],
    )
