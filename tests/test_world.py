import datetime as dt
import random

import pytest

from business_sim.config import default_world
from business_sim.world import SimError, fmt_money, poisson


def test_fmt_money():
    assert fmt_money(123_456) == "$1,234.56"
    assert fmt_money(5) == "$0.05"
    assert fmt_money(-5) == "-$0.05"
    assert fmt_money(0) == "$0.00"


def test_poisson_mean_is_close_to_lambda():
    rng = random.Random(42)
    samples = [poisson(rng, 4.0) for _ in range(20_000)]
    assert abs(sum(samples) / len(samples) - 4.0) < 0.1


def test_poisson_handles_zero_and_large_means():
    rng = random.Random(1)
    assert poisson(rng, 0) == 0
    assert all(poisson(rng, 100.0) >= 0 for _ in range(1_000))


def test_same_seed_gives_same_history_and_different_seed_differs():
    def history(seed):
        world = default_world(seed=seed)
        for _ in range(20):
            world.close_day()
        return world.cash_cents, [(e.day, e.kind, e.amount_cents) for e in world.ledger]

    assert history(7) == history(7)
    assert history(7) != history(8)


def test_ledger_reconciles_with_cash_balance():
    world = default_world(seed=3)
    world.place_order("RCS", "MUG-01", 24)
    for _ in range(15):
        world.close_day()
    assert world.opening_cash_cents + sum(e.amount_cents for e in world.ledger) == world.cash_cents


def test_delivery_arrives_after_lead_time():
    world = default_world(seed=1)
    world.products["MUG-01"].base_daily_demand = 0.0  # isolate the delivery from sales
    world.place_order("RCS", "MUG-01", 24)  # lead time 3 days, so it arrives on day 4
    for _ in range(3):
        world.close_day()
    assert world.products["MUG-01"].stock == 20
    world.close_day()
    assert world.products["MUG-01"].stock == 44


def test_order_rules_are_enforced():
    world = default_world()
    with pytest.raises(SimError, match="does not supply"):
        world.place_order("RCS", "TOTE-02", 10)
    with pytest.raises(SimError, match="at least"):
        world.place_order("RCS", "MUG-01", 5)
    with pytest.raises(SimError, match="insufficient cash"):
        world.place_order("BLK", "MUG-01", 1_000)
    with pytest.raises(SimError, match="unknown supplier"):
        world.place_order("NOPE", "MUG-01", 24)
    assert world.cash_cents == world.opening_cash_cents  # rejected orders cost nothing


def test_rent_is_charged_on_the_first_of_the_month():
    world = default_world(start_date=dt.date(2026, 11, 30))
    world.close_day()  # 30 November
    world.close_day()  # 1 December
    rent = [e for e in world.ledger if e.kind == "rent"]
    assert len(rent) == 1
    assert rent[0].date == "2026-12-01"


def test_sales_never_exceed_stock():
    world = default_world(seed=5)
    world.products["MUG-01"].base_daily_demand = 500.0
    world.close_day()
    assert world.products["MUG-01"].stock == 0
    sold = sum(e.units for e in world.ledger if e.kind == "sale" and e.sku == "MUG-01")
    assert sold == 20


def test_negative_cash_makes_the_business_insolvent():
    world = default_world()
    for product in world.products.values():
        product.base_daily_demand = 0.0  # no sales, so only overheads hit the balance
    world.cash_cents = 500  # utilities of $15.00 take it below zero
    world.close_day()
    assert world.insolvent
    with pytest.raises(SimError, match="insolvent"):
        world.close_day()


def test_set_price_validates_input():
    world = default_world()
    with pytest.raises(SimError, match="whole number"):
        world.set_price("MUG-01", 12.5)
    with pytest.raises(SimError, match="between"):
        world.set_price("MUG-01", 5)
    assert world.set_price("MUG-01", 1_300)["new_price"] == "$13.00"
