"""One simulated working day, seen from the operator's side."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from .tools import execute
from .world import World

# Tools that stay available after the day is closed (for updating notes).
AFTER_CLOSE_TOOLS = frozenset({"get_status", "read_notes", "write_notes"})


class RunLog:
    """Append-only JSON Lines transcript for one run. Does nothing when no directory is given."""

    def __init__(self, directory: Path | None):
        self._file = None
        if directory is not None:
            directory.mkdir(parents=True, exist_ok=True)
            self._file = (directory / "transcript.jsonl").open("a", encoding="utf-8")

    def event(self, kind: str, **fields: Any) -> None:
        if self._file is None:
            return
        record = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(), "type": kind, **fields}
        self._file.write(json.dumps(record, default=str) + "\n")
        self._file.flush()

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None


class Session:
    """The tool interface for one trading day. Operators act only through ``call``."""

    def __init__(self, world: World, log: RunLog):
        self.world = world
        self.log = log
        self.report: dict | None = None  # set when end_day succeeds

    @property
    def closed(self) -> bool:
        return self.report is not None

    def call(self, name: str, args: Any) -> tuple[Any, bool]:
        day = self.world.day
        if self.closed and name not in AFTER_CLOSE_TOOLS:
            result, is_error = {"error": "Today's books are closed. Trading tools reopen tomorrow."}, True
        else:
            result, is_error = execute(self.world, name, args)
            if name == "end_day" and not is_error:
                self.report = result
        self.log.event("tool", day=day, name=name, args=args, result=result, is_error=is_error)
        return result, is_error
