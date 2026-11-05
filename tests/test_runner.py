import copy
import json
from types import SimpleNamespace

from business_sim.config import default_world
from business_sim.operators import NUDGE, ClaudeOperator, RuleBasedOperator
from business_sim.session import RunLog, Session
from business_sim.simulation import Simulation


class FakeMessages:
    def __init__(self, scripted):
        self.scripted = list(scripted)
        self.calls = []

    def create(self, **kwargs):
        # Record a snapshot: the operator keeps appending to the same message list.
        self.calls.append(copy.deepcopy(kwargs))
        return self.scripted.pop(0)


class FakeClient:
    def __init__(self, scripted):
        self.messages = FakeMessages(scripted)


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def tool_block(block_id, name, args):
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=args)


def turn(*blocks, stop="tool_use"):
    return SimpleNamespace(content=list(blocks), stop_reason=stop, usage=None)


class IdleOperator:
    name = "idle"

    def run_day(self, session):
        return None


def test_rule_based_operator_runs_a_month_and_logs_everything(tmp_path):
    world = default_world(seed=11)
    run_dir = tmp_path / "run"
    summary = Simulation(world=world, operator=RuleBasedOperator(), out_dir=run_dir).run(30)

    assert summary["days_closed"] == 30
    assert not summary["insolvent"]
    assert summary["units_sold"] > 0
    assert world.day == 31

    events = [json.loads(line) for line in (run_dir / "transcript.jsonl").read_text().splitlines()]
    assert sum(1 for event in events if event["type"] == "day_closed") == 30
    assert json.loads((run_dir / "summary.json").read_text())["days_closed"] == 30
    assert json.loads((run_dir / "final_state.json").read_text())["seed"] == 11


def test_day_is_closed_automatically_if_the_operator_does_nothing():
    summary = Simulation(world=default_world(), operator=IdleOperator()).run(3)
    assert summary["days_closed"] == 3


def test_actions_after_end_day_are_refused_but_notes_stay_available():
    session = Session(default_world(), RunLog(None))
    session.call("end_day", {})

    result, is_error = session.call("place_order", {"supplier_id": "RCS", "sku": "MUG-01", "quantity": 24})
    assert is_error and "closed" in result["error"]

    _, is_error = session.call("read_notes", {})
    assert not is_error


def test_claude_operator_returns_tool_results_and_closes_the_day():
    client = FakeClient(
        [
            turn(tool_block("t1", "get_status", {})),
            turn(
                tool_block("t2", "place_order", {"supplier_id": "RCS", "sku": "MUG-01", "quantity": 24}),
                tool_block("t3", "end_day", {}),
            ),
        ]
    )
    world = default_world()
    summary = Simulation(world=world, operator=ClaudeOperator(model="test-model", client=client)).run(1)

    assert summary["days_closed"] == 1
    assert len(world.orders) == 1
    assert len(client.messages.calls) == 2
    assert client.messages.calls[0]["model"] == "test-model"

    # The second request carries the result of the first turn's tool call, keyed by its id.
    results = client.messages.calls[1]["messages"][-1]["content"]
    assert [r["tool_use_id"] for r in results] == ["t1"]
    assert all(r["type"] == "tool_result" for r in results)


def test_claude_operator_nudges_when_it_stops_without_closing_the_day():
    client = FakeClient(
        [
            turn(text_block("Checking the books first."), stop="end_turn"),
            turn(tool_block("t9", "end_day", {})),
        ]
    )
    Simulation(world=default_world(), operator=ClaudeOperator(client=client)).run(1)

    assert client.messages.calls[1]["messages"][-1] == {"role": "user", "content": NUDGE}
