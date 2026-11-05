import json
from dataclasses import asdict

from business_sim.config import default_world
from business_sim.manual import main
from business_sim.serialization import world_from_dict
from business_sim.world import fmt_money


def _canonical(obj):
    return json.dumps(obj, default=str, sort_keys=True)


def test_world_round_trips_through_json():
    world = default_world(seed=4)
    world.place_order("LTM", "TOTE-02", 10)
    for _ in range(5):
        world.close_day()
    world.write_notes("Reorder totes on Monday.")

    restored = world_from_dict(json.loads(json.dumps(asdict(world), default=str)))
    assert _canonical(asdict(restored)) == _canonical(asdict(world))


def test_manual_commands_match_the_in_memory_run(tmp_path, capsys):
    state = tmp_path / "state.json"
    assert main(["init", "--state", str(state), "--seed", "7"]) == 0
    for _ in range(3):
        assert main(["brief", "--state", str(state)]) == 0
        assert main(["call", "--state", str(state), "end_day"]) == 0
    capsys.readouterr()
    assert main(["summary", "--state", str(state)]) == 0
    manual_summary = json.loads(capsys.readouterr().out)

    expected = default_world(seed=7)
    for _ in range(3):
        expected.close_day()
    assert manual_summary["closing_cash"] == fmt_money(expected.cash_cents)
    assert manual_summary["days_closed"] == 3


def test_trading_is_refused_after_end_day_until_the_next_brief(tmp_path, capsys):
    state = tmp_path / "state.json"
    main(["init", "--state", str(state)])
    main(["brief", "--state", str(state)])
    main(["call", "--state", str(state), "end_day"])
    capsys.readouterr()

    order = json.dumps({"supplier_id": "RCS", "sku": "MUG-01", "quantity": 24})
    main(["call", "--state", str(state), "place_order", order])
    assert "closed" in json.loads(capsys.readouterr().out)["error"]

    main(["call", "--state", str(state), "read_notes"])
    assert "notes" in json.loads(capsys.readouterr().out)  # notes stay available

    main(["brief", "--state", str(state)])
    capsys.readouterr()
    main(["call", "--state", str(state), "place_order", order])
    assert json.loads(capsys.readouterr().out)["status"] == "in transit"


def test_init_refuses_to_overwrite_without_force(tmp_path, capsys):
    state = tmp_path / "state.json"
    assert main(["init", "--state", str(state)]) == 0
    assert main(["init", "--state", str(state)]) == 2
    assert "already exists" in capsys.readouterr().err
    assert main(["init", "--state", str(state), "--force"]) == 0


def test_every_call_is_logged_to_the_transcript(tmp_path, capsys):
    state = tmp_path / "state.json"
    main(["init", "--state", str(state)])
    main(["brief", "--state", str(state)])
    main(["call", "--state", str(state), "get_status"])
    events = [json.loads(line) for line in (tmp_path / "transcript.jsonl").read_text().splitlines()]
    assert [event["type"] for event in events] == ["briefing", "tool"]
    assert events[1]["name"] == "get_status"
