"""Command-line entry point: ``business-sim run --days 30``."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Sequence

from .config import default_world
from .operators import DEFAULT_MODEL, ClaudeOperator, RuleBasedOperator
from .simulation import Simulation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="business-sim", description="Run the simulated shop.")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="Run the simulation for a number of days.")
    run.add_argument("--days", type=int, default=30, help="Trading days to run (default: 30).")
    run.add_argument("--seed", type=int, default=1, help="Random seed for customer demand (default: 1).")
    run.add_argument(
        "--start-date",
        type=dt.date.fromisoformat,
        default=None,
        help="First trading date, YYYY-MM-DD (default: the built-in start date).",
    )
    run.add_argument(
        "--operator",
        choices=["rules", "claude"],
        default="rules",
        help="Who runs the shop: a fixed rule set (offline) or a Claude model (needs ANTHROPIC_API_KEY).",
    )
    run.add_argument("--model", default=DEFAULT_MODEL, help="Model for --operator claude.")
    run.add_argument("--out", default="runs", help="Directory for run logs (default: runs/).")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "run":
        return 2

    try:
        operator = ClaudeOperator(model=args.model) if args.operator == "claude" else RuleBasedOperator()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.out) / f"{stamp}-{args.operator}-seed{args.seed}"
    world = default_world(seed=args.seed, start_date=args.start_date)
    print(f"Running {args.days} day(s). Logs: {run_dir}", file=sys.stderr)

    summary = Simulation(world=world, operator=operator, out_dir=run_dir).run(args.days)
    print(json.dumps(summary, indent=2))
    return 0
