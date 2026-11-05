"""Regression tests for problems found in review."""

import json

import pytest

from business_sim.cli import main
from business_sim.config import default_world
from business_sim.simulation import Simulation
from business_sim.world import card_fees_cents


def test_card_fees_round_half_up_in_integer_cents():
    assert card_fees_cents(4_500, 0) == 131  # 2.9% of $45.00 is 130.5 cents, which rounds up
    assert card_fees_cents(4_500, 1) == 161  # plus 30 cents per order
    assert card_fees_cents(0, 0) == 0
    assert card_fees_cents(100_000, 3) == 2_990


def test_outputs_are_written_when_the_operator_fails(tmp_path):
    class FailingOperator:
        name = "failing"

        def run_day(self, session):
            if session.world.day == 2:
                raise RuntimeError("operator crashed")
            session.call("end_day", {})

    run_dir = tmp_path / "run"
    with pytest.raises(RuntimeError, match="operator crashed"):
        Simulation(world=default_world(), operator=FailingOperator(), out_dir=run_dir).run(3)

    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["days_closed"] == 1
    assert (run_dir / "final_state.json").exists()


def test_cli_rejects_zero_days(tmp_path, capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["run", "--days", "0", "--out", str(tmp_path)])
    assert excinfo.value.code == 2
    assert "must be at least 1" in capsys.readouterr().err
