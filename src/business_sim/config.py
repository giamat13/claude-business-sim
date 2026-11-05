"""The default business: a three-product online shop with three suppliers."""

from __future__ import annotations

import datetime as dt

from .world import Product, Supplier, SupplierOffer, World, fmt_money

DEFAULT_START_DATE = dt.date(2026, 11, 2)
OPENING_CASH_CENTS = 300_000  # $3,000.00


def default_world(seed: int = 1, start_date: dt.date | None = None) -> World:
    products = {
        "MUG-01": Product(
            sku="MUG-01",
            name="Ceramic mug, 350 ml",
            price_cents=1_200,
            stock=20,
            reference_price_cents=1_200,
            base_daily_demand=6.0,
            elasticity=-1.4,
        ),
        "TOTE-02": Product(
            sku="TOTE-02",
            name="Canvas tote bag",
            price_cents=1_800,
            stock=10,
            reference_price_cents=1_800,
            base_daily_demand=3.0,
            elasticity=-1.1,
        ),
        "NOTE-03": Product(
            sku="NOTE-03",
            name="A5 dotted notebook",
            price_cents=900,
            stock=20,
            reference_price_cents=900,
            base_daily_demand=5.0,
            elasticity=-1.8,
        ),
    }
    suppliers = {
        "RCS": Supplier(
            supplier_id="RCS",
            name="Riverside Ceramics Studio",
            email="orders@riverside-ceramics.example",
            offers=[SupplierOffer("MUG-01", unit_cost_cents=430, lead_time_days=3, min_order_qty=24)],
        ),
        "LTM": Supplier(
            supplier_id="LTM",
            name="Linden Textile Mill",
            email="sales@linden-textile.example",
            offers=[
                SupplierOffer("TOTE-02", unit_cost_cents=650, lead_time_days=5, min_order_qty=10),
                SupplierOffer("NOTE-03", unit_cost_cents=180, lead_time_days=2, min_order_qty=20),
            ],
        ),
        "BLK": Supplier(
            supplier_id="BLK",
            name="Budget Blanks Ltd.",
            email="trade@budget-blanks.example",
            offers=[
                SupplierOffer("MUG-01", unit_cost_cents=390, lead_time_days=9, min_order_qty=50),
                SupplierOffer("NOTE-03", unit_cost_cents=165, lead_time_days=7, min_order_qty=100),
            ],
        ),
    }
    world = World(
        start_date=start_date or DEFAULT_START_DATE,
        seed=seed,
        opening_cash_cents=OPENING_CASH_CENTS,
        cash_cents=OPENING_CASH_CENTS,
        products=products,
        suppliers=suppliers,
    )
    world.post_message(
        sender="Juniper Business Banking",
        address="accounts@juniper-business.example",
        subject="Your business account is open",
        body=(
            "Welcome. Your business current account is open with a balance of "
            f"{fmt_money(OPENING_CASH_CENTS)}."
        ),
    )
    return world
