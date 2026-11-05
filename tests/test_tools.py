from business_sim.config import default_world
from business_sim.tools import TOOL_SPECS, execute


def test_every_tool_spec_has_a_handler():
    world = default_world()
    for spec in TOOL_SPECS:
        result, _ = execute(world, spec["name"], {})
        assert "unknown tool" not in str(result), spec["name"]


def test_unknown_tool_and_bad_arguments_are_errors_not_crashes():
    world = default_world()
    assert execute(world, "launch_rocket", {}) == ({"error": "unknown tool 'launch_rocket'"}, True)

    result, is_error = execute(world, "set_price", {"sku": "MUG-01"})
    assert is_error and "missing required argument 'price_cents'" in result["error"]

    result, is_error = execute(world, "set_price", {"sku": "MUG-01", "price_cents": 12.0})
    assert is_error and "integer" in result["error"]

    result, is_error = execute(world, "get_status", {"extra": 1})
    assert is_error and "unexpected argument 'extra'" in result["error"]


def test_end_day_returns_the_day_report():
    world = default_world()
    report, is_error = execute(world, "end_day", {})
    assert not is_error
    assert report["day"] == 1
    assert world.day == 2


def test_email_only_reaches_known_addresses():
    world = default_world()
    result, is_error = execute(
        world,
        "send_email",
        {"to": "stranger@elsewhere.example", "subject": "Hi", "body": "Hello"},
    )
    assert is_error and "unknown recipient" in result["error"]

    result, is_error = execute(
        world,
        "send_email",
        {"to": "orders@riverside-ceramics.example", "subject": "Restock", "body": "Hello"},
    )
    assert not is_error and result["status"] == "sent"


def test_notes_are_limited_in_length():
    world = default_world()
    result, is_error = execute(world, "write_notes", {"text": "x" * 4_001})
    assert is_error and "too long" in result["error"]
    result, is_error = execute(world, "write_notes", {"text": "Reorder mugs on Monday."})
    assert not is_error
