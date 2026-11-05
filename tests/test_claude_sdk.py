"""Exercises ClaudeOperator through the real anthropic SDK, against a local stub of the Messages API.

This checks request and response wire format only (tool_use blocks round-trip, tool_result blocks are
well formed). It says nothing about how a real model behaves.
"""

import pytest

anthropic = pytest.importorskip("anthropic")

from business_sim.config import default_world  # noqa: E402
from business_sim.operators import ClaudeOperator  # noqa: E402
from business_sim.simulation import Simulation  # noqa: E402

from conftest import stub_message  # noqa: E402


def test_claude_operator_runs_a_day_through_the_real_sdk(stub_api):
    stub_api.replies = [
        stub_message(
            [
                {"type": "text", "text": "Checking stock first."},
                {"type": "tool_use", "id": "toolu_1", "name": "list_products", "input": {}},
            ]
        ),
        stub_message(
            [
                {
                    "type": "tool_use",
                    "id": "toolu_2",
                    "name": "place_order",
                    "input": {"supplier_id": "RCS", "sku": "MUG-01", "quantity": 24},
                },
                {"type": "tool_use", "id": "toolu_3", "name": "end_day", "input": {}},
            ]
        ),
    ]
    client = anthropic.Anthropic(
        api_key="stub-key",
        base_url=f"http://127.0.0.1:{stub_api.server_port}",
        max_retries=0,
    )
    world = default_world()
    summary = Simulation(world=world, operator=ClaudeOperator(model="stub-model", client=client)).run(1)

    assert summary["days_closed"] == 1
    assert len(world.orders) == 1

    first, second = stub_api.requests
    assert first["model"] == "stub-model"
    assert "Harbor & Thread" in first["system"]
    assert {tool["name"] for tool in first["tools"]} >= {"place_order", "end_day"}

    # The assistant turn comes back with its text and tool_use blocks intact.
    assistant_turn = second["messages"][1]
    assert assistant_turn["role"] == "assistant"
    assert [block["type"] for block in assistant_turn["content"]] == ["text", "tool_use"]
    assert assistant_turn["content"][1]["id"] == "toolu_1"

    # Its tool results follow, keyed by the tool_use ids.
    results_turn = second["messages"][2]
    assert results_turn["role"] == "user"
    assert [block["tool_use_id"] for block in results_turn["content"]] == ["toolu_1"]
    assert all(block["type"] == "tool_result" for block in results_turn["content"])
    assert all(block["is_error"] is False for block in results_turn["content"])
