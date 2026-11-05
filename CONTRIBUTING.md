# Contributing

Thanks for your interest in business-sim. Small, focused changes are the easiest to review.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,claude]"
pytest
```

The test suite runs offline. Tests that exercise the Claude operator talk to a local stub of the Messages API, so no API key or network access is needed.

## Ground rules

- **Keep the simulation deterministic.** Any new randomness should come from a `random.Random` seeded from the world's seed and the day, the way `World.close_day` does it. A run with the same seed and the same operator decisions must produce the same history.
- **Use integer cents for money.** Do not introduce floats into ledger amounts.
- **Stay local.** Apart from the Claude operator's model calls, do not add code that makes network calls, touches real payment or email services, or sends mail to addresses outside the reserved `.example` domains. The operator should only be able to change the world through the tools in `tools.py`.
- **Tool errors are data.** Expected rule violations should raise `SimError` so the operator receives a tool error. Reserve other exceptions for bugs in the simulator.
- **Add tests with behaviour changes.** If you change economics, add a test that pins the new rule.

## Style

- Python 3.10+, type hints on public functions, `from __future__ import annotations`.
- Standard library only in `src/`. Optional dependencies belong in `pyproject.toml` extras.
- Keep modules small and focused; match the existing naming.

## Pull requests

- Describe what changed and why.
- Include the commands you ran (for example, `pytest` and a short `business-sim run`).
- If your change affects the economics or the tool interface, note it in the description so reviewers can check the effect on existing runs.
