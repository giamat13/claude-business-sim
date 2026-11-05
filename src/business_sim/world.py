"""Economic state and rules for the simulated business.

Money is stored as integer cents so arithmetic never drifts. Nothing in this
module touches the network, the file system, or any real payment rail.
"""

from __future__ import annotations

import datetime as dt
import math
import random
from dataclasses import dataclass, field

SALES_FEE_RATE = 0.029  # card processor: 2.9% of revenue...
SALES_FEE_PER_UNIT_CENTS = 30  # ...plus 30 cents per order (one unit = one order)
DAILY_UTILITIES_CENTS = 1_500
MONTHLY_RENT_CENTS = 120_000  # charged on the 1st of each month
LOW_STOCK_THRESHOLD = 5
MIN_PRICE_CENTS = 100
MAX_PRICE_CENTS = 100_000
MAX_NOTES_CHARS = 4_000
INBOX_PAGE_SIZE = 50
CUSTOMER_EMAIL_CHANCE = 0.25

# Demand multiplier by weekday, Monday first.
WEEKDAY_DEMAND = (0.9, 0.9, 1.0, 1.0, 1.1, 1.4, 1.3)

INVENTORY_SENDER = "Inventory system"
INVENTORY_ADDRESS = "inventory-alerts@harbor-and-thread.example"

CUSTOMER_NAMES = (
    "Maya Cohen",
    "Daniel Park",
    "Sofia Rossi",
    "Liam O'Brien",
    "Aisha Khan",
    "Noah Berg",
)

CUSTOMER_EMAILS = (
    ("Do your mugs come in other colours?", "Hi, I love the mug. Are you planning other colours? Thanks!"),
    ("Delivery time question", "Hi, I ordered last week and wanted to check the expected delivery window."),
    ("Bulk order", "Hi, I am buying gifts for a team of 15. Do you offer a discount on notebooks?"),
    ("Damaged item", "My tote arrived with a small tear in the seam. What should I do?"),
    ("Thank you", "Just wanted to say thanks, the notebook is great!"),
    ("Wholesale enquiry", "Do you sell wholesale to cafes? We would order mugs every month."),
)


class SimError(Exception):
    """A business rule was broken. The operator sees this as a tool error, not a crash."""


def fmt_money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    dollars, remainder = divmod(abs(cents), 100)
    return f"{sign}${dollars:,}.{remainder:02d}"


def poisson(rng: random.Random, lam: float) -> int:
    """Draw a Poisson-distributed count. Uses Knuth's method, or a normal approximation for large means."""
    if lam <= 0:
        return 0
    if lam > 60:
        return max(0, round(rng.gauss(lam, math.sqrt(lam))))
    limit = math.exp(-lam)
    count = 0
    product = 1.0
    while True:
        product *= rng.random()
        if product <= limit:
            return count
        count += 1


def customer_address(name: str) -> str:
    slug = name.lower().replace("'", "").replace(" ", ".")
    return f"{slug}@customers.example"


@dataclass
class Product:
    sku: str
    name: str
    price_cents: int
    stock: int
    reference_price_cents: int  # the price at which base_daily_demand is observed
    base_daily_demand: float  # expected units per day at the reference price
    elasticity: float  # negative; demand scales with (price / reference) ** elasticity


@dataclass
class SupplierOffer:
    sku: str
    unit_cost_cents: int
    lead_time_days: int
    min_order_qty: int


@dataclass
class Supplier:
    supplier_id: str
    name: str
    email: str
    offers: list[SupplierOffer]


@dataclass
class PurchaseOrder:
    order_id: str
    supplier_id: str
    sku: str
    quantity: int
    unit_cost_cents: int
    placed_day: int
    arrives_day: int
    delivered: bool = False


@dataclass
class LedgerEntry:
    day: int
    date: str
    kind: str  # sale, fee, purchase, rent, utilities
    amount_cents: int  # positive = money in, negative = money out
    description: str
    sku: str | None = None
    units: int = 0


@dataclass
class Message:
    message_id: int
    day: int
    sender: str
    address: str
    subject: str
    body: str
    read: bool = False


@dataclass
class World:
    start_date: dt.date
    seed: int
    opening_cash_cents: int
    cash_cents: int
    products: dict[str, Product]
    suppliers: dict[str, Supplier]
    day: int = 1  # the day currently open for trading; starts at 1
    orders: list[PurchaseOrder] = field(default_factory=list)
    ledger: list[LedgerEntry] = field(default_factory=list)
    inbox: list[Message] = field(default_factory=list)
    outbox: list[dict] = field(default_factory=list)
    notes: str = ""
    insolvent: bool = False
    next_id: int = 1

    # ----- time and bookkeeping helpers -------------------------------------

    @property
    def date(self) -> dt.date:
        return self.date_for_day(self.day)

    def date_for_day(self, day: int) -> dt.date:
        return self.start_date + dt.timedelta(days=day - 1)

    def _new_id(self) -> int:
        value = self.next_id
        self.next_id += 1
        return value

    def _post(
        self,
        kind: str,
        amount_cents: int,
        description: str,
        sku: str | None = None,
        units: int = 0,
    ) -> None:
        self.cash_cents += amount_cents
        self.ledger.append(
            LedgerEntry(self.day, self.date.isoformat(), kind, amount_cents, description, sku, units)
        )

    def post_message(self, sender: str, address: str, subject: str, body: str) -> Message:
        message = Message(self._new_id(), self.day, sender, address, subject, body)
        self.inbox.append(message)
        return message

    def _product(self, sku: str) -> Product:
        if sku not in self.products:
            raise SimError(f"unknown sku {sku!r}")
        return self.products[sku]

    def _supplier(self, supplier_id: str) -> Supplier:
        if supplier_id not in self.suppliers:
            raise SimError(f"unknown supplier_id {supplier_id!r}")
        return self.suppliers[supplier_id]

    def _has_open_order(self, sku: str) -> bool:
        return any(order.sku == sku and not order.delivered for order in self.orders)

    def _known_addresses(self) -> set[str]:
        addresses = {supplier.email for supplier in self.suppliers.values()}
        addresses.update(message.address for message in self.inbox)
        return addresses

    def _order_view(self, order: PurchaseOrder) -> dict:
        total = order.quantity * order.unit_cost_cents
        return {
            "order_id": order.order_id,
            "supplier_id": order.supplier_id,
            "sku": order.sku,
            "quantity": order.quantity,
            "unit_cost": fmt_money(order.unit_cost_cents),
            "total": fmt_money(total),
            "placed_on": self.date_for_day(order.placed_day).isoformat(),
            "arrives_on": self.date_for_day(order.arrives_day).isoformat(),
            "status": "delivered" if order.delivered else "in transit",
        }

    # ----- operator-facing actions ------------------------------------------

    def status(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "day": self.day,
            "cash": fmt_money(self.cash_cents),
            "cash_cents": self.cash_cents,
            "insolvent": self.insolvent,
            "unread_messages": sum(1 for message in self.inbox if not message.read),
            "orders_in_transit": sum(1 for order in self.orders if not order.delivered),
        }

    def list_products(self) -> list[dict]:
        return [
            {
                "sku": product.sku,
                "name": product.name,
                "price": fmt_money(product.price_cents),
                "price_cents": product.price_cents,
                "stock": product.stock,
            }
            for product in sorted(self.products.values(), key=lambda p: p.sku)
        ]

    def set_price(self, sku: str, price_cents: int) -> dict:
        product = self._product(sku)
        if isinstance(price_cents, bool) or not isinstance(price_cents, int):
            raise SimError("price_cents must be a whole number of cents")
        if not MIN_PRICE_CENTS <= price_cents <= MAX_PRICE_CENTS:
            raise SimError(
                f"price must be between {fmt_money(MIN_PRICE_CENTS)} and {fmt_money(MAX_PRICE_CENTS)}"
            )
        old_price = product.price_cents
        product.price_cents = price_cents
        return {"sku": sku, "old_price": fmt_money(old_price), "new_price": fmt_money(price_cents)}

    def list_suppliers(self) -> list[dict]:
        return [
            {
                "supplier_id": supplier.supplier_id,
                "name": supplier.name,
                "email": supplier.email,
                "offers": [
                    {
                        "sku": offer.sku,
                        "unit_cost": fmt_money(offer.unit_cost_cents),
                        "unit_cost_cents": offer.unit_cost_cents,
                        "min_order_qty": offer.min_order_qty,
                        "lead_time_days": offer.lead_time_days,
                    }
                    for offer in supplier.offers
                ],
            }
            for supplier in self.suppliers.values()
        ]

    def place_order(self, supplier_id: str, sku: str, quantity: int) -> dict:
        supplier = self._supplier(supplier_id)
        offer = next((o for o in supplier.offers if o.sku == sku), None)
        if offer is None:
            raise SimError(f"{supplier.name} does not supply {sku}")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
            raise SimError("quantity must be a positive whole number")
        if quantity < offer.min_order_qty:
            raise SimError(f"{supplier.name} requires at least {offer.min_order_qty} units of {sku}")
        cost = quantity * offer.unit_cost_cents
        if cost > self.cash_cents:
            raise SimError(
                f"insufficient cash: the order costs {fmt_money(cost)} "
                f"and the balance is {fmt_money(self.cash_cents)}"
            )
        order = PurchaseOrder(
            order_id=f"PO-{self._new_id():05d}",
            supplier_id=supplier_id,
            sku=sku,
            quantity=quantity,
            unit_cost_cents=offer.unit_cost_cents,
            placed_day=self.day,
            arrives_day=self.day + offer.lead_time_days,
        )
        self.orders.append(order)
        self._post(
            "purchase",
            -cost,
            f"{order.order_id}: {quantity} x {sku} from {supplier.name}",
            sku=sku,
            units=quantity,
        )
        self.post_message(
            supplier.name,
            supplier.email,
            f"Order confirmation {order.order_id}",
            (
                "Thank you for your order.\n\n"
                f"{quantity} x {sku} at {fmt_money(offer.unit_cost_cents)} each, "
                f"total {fmt_money(cost)}, paid.\n"
                f"Expected delivery: {self.date_for_day(order.arrives_day):%A %d %B %Y}."
            ),
        )
        return self._order_view(order)

    def list_orders(self) -> list[dict]:
        return [self._order_view(order) for order in reversed(self.orders)]

    def sales_report(self, last_days: int = 7) -> dict:
        first_day = max(1, self.day - last_days)
        totals = {
            sku: {"sku": sku, "units": 0, "revenue_cents": 0, "fees_cents": 0}
            for sku in sorted(self.products)
        }
        for entry in self.ledger:
            if entry.sku is None or not first_day <= entry.day < self.day:
                continue
            if entry.kind == "sale":
                totals[entry.sku]["units"] += entry.units
                totals[entry.sku]["revenue_cents"] += entry.amount_cents
            elif entry.kind == "fee":
                totals[entry.sku]["fees_cents"] += entry.amount_cents
        rows = [
            {
                "sku": row["sku"],
                "units": row["units"],
                "revenue": fmt_money(row["revenue_cents"]),
                "card_fees": fmt_money(row["fees_cents"]),
                "net": fmt_money(row["revenue_cents"] + row["fees_cents"]),
            }
            for row in totals.values()
        ]
        if first_day >= self.day:
            period = "no completed days yet"
        else:
            period = f"day {first_day} to day {self.day - 1}"
        total_revenue = sum(row["revenue_cents"] for row in totals.values())
        total_fees = sum(row["fees_cents"] for row in totals.values())
        return {
            "period": period,
            "by_product": rows,
            "total_units": sum(row["units"] for row in totals.values()),
            "total_revenue": fmt_money(total_revenue),
            "total_card_fees": fmt_money(total_fees),
        }

    def get_ledger(self, limit: int = 20) -> list[dict]:
        return [
            {
                "date": entry.date,
                "kind": entry.kind,
                "amount": fmt_money(entry.amount_cents),
                "amount_cents": entry.amount_cents,
                "description": entry.description,
            }
            for entry in reversed(self.ledger[-limit:])
        ]

    def read_inbox(self, unread_only: bool = False) -> list[dict]:
        selected = [m for m in self.inbox if not (unread_only and m.read)][-INBOX_PAGE_SIZE:]
        for message in selected:
            message.read = True
        return [
            {
                "message_id": message.message_id,
                "date": self.date_for_day(message.day).isoformat(),
                "from": message.sender,
                "address": message.address,
                "subject": message.subject,
                "body": message.body,
            }
            for message in reversed(selected)
        ]

    def send_email(self, to: str, subject: str, body: str) -> dict:
        if to not in self._known_addresses():
            raise SimError(
                f"unknown recipient {to!r}: you can email suppliers and customers who have written to you"
            )
        if not subject.strip():
            raise SimError("subject must not be empty")
        record = {
            "status": "sent",
            "date": self.date.isoformat(),
            "to": to,
            "subject": subject,
            "body": body,
        }
        self.outbox.append(record)
        return record

    def read_notes(self) -> dict:
        return {"notes": self.notes}

    def write_notes(self, text: str) -> dict:
        if len(text) > MAX_NOTES_CHARS:
            raise SimError(f"notes are limited to {MAX_NOTES_CHARS} characters")
        self.notes = text
        return {"saved_characters": len(text)}

    # ----- end of day --------------------------------------------------------

    def close_day(self) -> dict:
        """Close the open day: deliveries, customer purchases, overheads, then move to the next day."""
        if self.insolvent:
            raise SimError("the business is insolvent and can no longer trade")

        rng = random.Random(f"{self.seed}:{self.day}")
        today = self.date
        closed_day = self.day
        report: dict = {"day": closed_day, "date": today.isoformat(), "deliveries": [], "sales": []}

        for order in self.orders:
            if order.delivered or order.arrives_day > self.day:
                continue
            order.delivered = True
            self.products[order.sku].stock += order.quantity
            supplier = self.suppliers[order.supplier_id]
            report["deliveries"].append(
                {"order_id": order.order_id, "sku": order.sku, "quantity": order.quantity}
            )
            self.post_message(
                supplier.name,
                supplier.email,
                f"Delivery notice {order.order_id}",
                f"{order.quantity} x {order.sku} delivered to your warehouse today.",
            )

        weekday_factor = WEEKDAY_DEMAND[today.weekday()]
        for sku in sorted(self.products):
            product = self.products[sku]
            expected = (
                product.base_daily_demand
                * (product.price_cents / product.reference_price_cents) ** product.elasticity
                * weekday_factor
            )
            demand = poisson(rng, expected)
            units = min(demand, product.stock)
            product.stock -= units
            if units:
                revenue = units * product.price_cents
                fees = round(revenue * SALES_FEE_RATE) + SALES_FEE_PER_UNIT_CENTS * units
                self._post(
                    "sale",
                    revenue,
                    f"{units} x {sku} at {fmt_money(product.price_cents)}",
                    sku=sku,
                    units=units,
                )
                self._post("fee", -fees, f"Card processing on {units} x {sku}", sku=sku)
            report["sales"].append({"sku": sku, "units": units, "stock_left": product.stock})

            if product.stock == 0:
                self.post_message(
                    INVENTORY_SENDER,
                    INVENTORY_ADDRESS,
                    f"Out of stock: {sku}",
                    f"{product.name} ({sku}) is out of stock.",
                )
            elif product.stock <= LOW_STOCK_THRESHOLD and not self._has_open_order(sku):
                self.post_message(
                    INVENTORY_SENDER,
                    INVENTORY_ADDRESS,
                    f"Low stock: {sku}",
                    f"{product.name} ({sku}) has {product.stock} units left and nothing on order.",
                )

        self._post("utilities", -DAILY_UTILITIES_CENTS, "Utilities")
        if today.day == 1:
            self._post("rent", -MONTHLY_RENT_CENTS, f"Rent, {today:%B %Y}")

        if rng.random() < CUSTOMER_EMAIL_CHANCE:
            name = rng.choice(CUSTOMER_NAMES)
            subject, body = rng.choice(CUSTOMER_EMAILS)
            self.post_message(name, customer_address(name), subject, body)

        report["bank_entries"] = [
            {"kind": entry.kind, "amount": fmt_money(entry.amount_cents), "description": entry.description}
            for entry in self.ledger
            if entry.day == closed_day
        ]

        self.day += 1
        if self.cash_cents < 0:
            self.insolvent = True
        report["cash_at_close"] = fmt_money(self.cash_cents)
        report["insolvent"] = self.insolvent
        return report
