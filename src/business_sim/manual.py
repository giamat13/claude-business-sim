"""Run the shop one command at a time, with the state kept in a JSON file.

This lets someone other than the built-in operators act as the operator. Each command loads the state,
does one thing, and saves the state again. A session starts with ``brief`` and ends when ``end_day``
succeeds. Trading tools are refused for the rest of that session, as in ``Session``.

Commands::

    python -m business_sim.manual init    --state FILE [--seed N] [--start-date YYYY-MM-DD] [--force]
    python -m business_sim.manual tools   --state FILE
    python -m business_sim.manual brief   --state FILE
    python -m business_sim.manual call    --state FILE NAME [ARGS_JSON]
    python -m business_sim.manual summary --state FILE

Every call is appended to ``transcript.jsonl`` next to the state file.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from .config import default_world
from .operators import morning_message
from .serialization import world_from_dict
from .session import AFTER_CLOSE_TOOLS
from .simulation import Simulation
from .tools import TOOL_SPECS, execute


class _NamedOperator:
    """Stands in for an operator so ``Simulation.summary`` can label the run."""

    name = "manual"


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, state: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def _log(state_path: Path, record: dict[str, Any]) -> None:
    with (state_path.parent / "transcript.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"ts": _now(), **record}, default=str) + "\n")


def _emit(payload: Any) -> None:
    print(json.dumps(payload, indent=2, default=str))


def cmd_init(args: argparse.Namespace) -> int:
    path = Path(args.state)
    if path.exists() and not args.force:
        print(f"error: {path} already exists (use --force to replace it)", file=sys.stderr)
        return 2
    path.parent.mkdir(parents=True, exist_ok=True)
    world = default_world(seed=args.seed, start_date=args.start_date)
    _save(path, {"world": asdict(world), "session_closed": False})
    _emit({"initialized": str(path), "seed": args.seed, "start_date": world.start_date.isoformat()})
    return 0


def cmd_tools(args: argparse.Namespace) -> int:
    _emit(TOOL_SPECS)
    return 0


def cmd_brief(args: argparse.Namespace) -> int:
    path = Path(args.state)
    state = _load(path)
    world = world_from_dict(state["world"])
    state["session_closed"] = False
    _save(path, state)
    text = morning_message(world)
    _log(path, {"type": "briefing", "day": world.day, "text": text})
    print(text)
    return 0


def cmd_call(args: argparse.Namespace) -> int:
    path = Path(args.state)
    state = _load(path)
    world = world_from_dict(state["world"])
    try:
        call_args = json.loads(args.args_json)
    except json.JSONDecodeError as exc:
        result, is_error = {"error": f"arguments must be valid JSON: {exc}"}, True
    else:
        day = world.day
        if state["session_closed"] and args.name not in AFTER_CLOSE_TOOLS:
            result, is_error = {"error": "Today's books are closed. Trading tools reopen tomorrow."}, True
        else:
            result, is_error = execute(world, args.name, call_args)
            if args.name == "end_day" and not is_error:
                state["session_closed"] = True
        _log(path, {"type": "tool", "day": day, "name": args.name, "args": call_args, "result": result,
                    "is_error": is_error})
    state["world"] = asdict(world)
    _save(path, state)
    _emit(result)
    return 0  # tool errors are results the operator reads, not failures of the command


def cmd_summary(args: argparse.Namespace) -> int:
    world = world_from_dict(_load(Path(args.state))["world"])
    simulation = Simulation(world=world, operator=_NamedOperator())
    _emit(simulation.summary(days_closed=world.day - 1))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="business_sim.manual", description="Operate the shop one command at a time.")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="Create a new shop state file.")
    init.add_argument("--state", required=True)
    init.add_argument("--seed", type=int, default=1)
    init.add_argument("--start-date", type=dt.date.fromisoformat, default=None)
    init.add_argument("--force", action="store_true", help="Replace an existing state file.")
    init.set_defaults(handler=cmd_init)

    tools = commands.add_parser("tools", help="Print the tool definitions.")
    tools.set_defaults(handler=cmd_tools)

    brief = commands.add_parser("brief", help="Start a session and print the morning briefing.")
    brief.add_argument("--state", required=True)
    brief.set_defaults(handler=cmd_brief)

    call = commands.add_parser("call", help="Run one tool.")
    call.add_argument("--state", required=True)
    call.add_argument("name")
    call.add_argument("args_json", nargs="?", default="{}", metavar="ARGS_JSON")
    call.set_defaults(handler=cmd_call)

    summary = commands.add_parser("summary", help="Print the run summary so far.")
    summary.add_argument("--state", required=True)
    summary.set_defaults(handler=cmd_summary)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
