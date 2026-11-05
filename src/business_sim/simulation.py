"""Runs the business day by day with a given operator."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .operators import Operator
from .session import RunLog, Session
from .world import World, fmt_money


@dataclass
class Simulation:
    world: World
    operator: Operator
    out_dir: Path | None = None

    def run(self, days: int) -> dict:
        if days < 1:
            raise ValueError("days must be at least 1")

        log = RunLog(self.out_dir)
        closed_days = 0
        try:
            for _ in range(days):
                if self.world.insolvent:
                    break
                session = Session(self.world, log)
                self.operator.run_day(session)
                if not session.closed:
                    log.event("forced_end_day", day=self.world.day)
                    session.call("end_day", {})
                if not session.closed:
                    raise RuntimeError(f"could not close day {self.world.day}")
                closed_days += 1
                log.event("day_closed", report=session.report)
        finally:
            log.close()

        summary = self.summary(closed_days)
        if self.out_dir is not None:
            (self.out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            (self.out_dir / "final_state.json").write_text(
                json.dumps(asdict(self.world), indent=2, default=str), encoding="utf-8"
            )
        return summary

    def summary(self, days_closed: int) -> dict:
        world = self.world
        units_sold = sum(entry.units for entry in world.ledger if entry.kind == "sale")
        change = world.cash_cents - world.opening_cash_cents
        return {
            "operator": self.operator.name,
            "seed": world.seed,
            "start_date": world.start_date.isoformat(),
            "days_closed": days_closed,
            "next_trading_day": world.date.isoformat(),
            "insolvent": world.insolvent,
            "opening_cash": fmt_money(world.opening_cash_cents),
            "closing_cash": fmt_money(world.cash_cents),
            "cash_change": fmt_money(change),
            "cash_change_cents": change,
            "units_sold": units_sold,
            "note": "cash_change ignores stock on hand, so it is not an accounting profit.",
        }
