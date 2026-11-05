# business-sim

A small, self-contained simulation of an online shop. An operator runs it through the same kind of tool interface a real operator would use: it sets prices, buys stock from suppliers, reads and sends email, keeps notes, and closes each day. The operator can be a fixed rule set (offline) or a Claude model.

The world moves on its own between the operator's decisions. Customers buy according to price and stock, deliveries arrive after supplier lead times, and rent and utilities are charged on schedule. Every run is reproducible from its seed.

> **This is a simulation.** Nothing here connects to the internet, a bank, a payment processor, or email. See [Responsible use](#responsible-use).

## Quick start

Requires Python 3.10 or newer. There are no runtime dependencies.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest

# Offline run with the rule-based operator (no API key needed)
business-sim run --days 30 --operator rules
```

### Running with a Claude model

```bash
pip install -e ".[claude]"
export ANTHROPIC_API_KEY=your-key-here

business-sim run --days 10 --operator claude --model claude-opus-5-5
```

Each simulated day is a conversation of several model calls, billed at your API rates. Start with a few days to see what a run costs before doing longer ones.

## What the operator sees

The operator gets a briefing each morning (a short description of the shop, its status, and its own notes from earlier days), then works through tools until it calls `end_day`.

| Tool | What it does |
| --- | --- |
| `get_status` | Date, cash balance, unread messages, orders in transit |
| `list_products` | Products with selling price and stock on hand |
| `set_price` | Change a product's price; applies immediately |
| `list_suppliers` | Supplier unit costs, minimum order quantities, lead times |
| `place_order` | Buy stock; invoice paid at once, goods arrive after lead time |
| `list_orders` | Purchase orders and their status |
| `sales_report` | Units, revenue and card fees for recently completed days |
| `get_ledger` | Recent bank entries |
| `read_inbox` | Email from suppliers, customers and internal alerts |
| `send_email` | Email a supplier, or a customer who has written in |
| `read_notes` / `write_notes` | Persistent notes (the only memory carried between days) |
| `end_day` | Close the books and advance to the next day |

Rule violations, such as ordering without enough cash or setting an out-of-range price, come back as tool errors rather than crashes.

## How the economics work

- **One step per day.** During the day the operator acts. `end_day` then runs, in order: deliveries arrive, customers buy, overheads are paid, customer email may arrive, and the date advances.
- **Demand** for each product is a Poisson draw around an expected value. That expected value falls as the price rises (constant elasticity, which differs per product) and is higher at weekends. Sales are capped by stock, and unmet demand is lost.
- **Money** is stored as integer cents. Purchases are paid when ordered. Card fees come out of sales. Utilities are charged daily and rent on the 1st of each month.
- **Insolvency.** If the balance is negative at the close of a day, the business is insolvent and the run stops.
- **Memory.** Each day starts a fresh conversation for the operator. Only its notes carry over. This keeps prompts short and makes the memory constraint explicit.
- **Determinism.** Customer demand and emails are seeded per day from `--seed`, so the same seed and the same operator decisions give the same history.

The default business (Harbor & Thread Co.) is defined in [`src/business_sim/config.py`](src/business_sim/config.py). It has three products, three suppliers, $3,000 opening cash, and a start date of 2 November 2026. Change any of these to build a different shop.

## Output

Each run writes to `runs/<timestamp>-<operator>-seed<seed>/`:

- `transcript.jsonl`: every briefing, model message, tool call and result, and end-of-day report, one JSON object per line.
- `summary.json`: opening and closing cash, cash change, units sold, and whether the business became insolvent.
- `final_state.json`: the full world state at the end of the run.

`cash_change` ignores stock on hand, so it is not an accounting profit.

## Project layout

```
src/business_sim/
  world.py       economic state and rules (money, stock, orders, demand, close of day)
  config.py      the default business: products, suppliers, opening cash
  tools.py       tool schemas and the validator that runs them
  session.py     one trading day as seen by the operator; transcript logging
  operators.py   RuleBasedOperator and ClaudeOperator
  prompts.py     the operator's daily briefing
  simulation.py  runs days in a loop and writes the summary
  cli.py         the `business-sim` command
tests/           unit and integration tests (no network or API key needed)
```

## Responsible use

- **Everything is local.** The tools only change the simulated world in memory and on disk. Email addresses use reserved `.example` domains, so no message can reach a real person. Keep it that way. Connecting these tools to real accounts, money, customers or email would make the operator's actions real.
- **The briefing frames the shop as a real business.** That is deliberate for this kind of experiment. Results describe behaviour under that framing, so say so if you publish them.
- **Model calls cost money.** The `claude` operator bills against your Anthropic API account.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues and pull requests are welcome.

## License

MIT. See [LICENSE](LICENSE).
