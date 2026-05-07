# Examples

This folder contains a small synthetic demo for validating the public backtester workflow. It is not a Prosperity competition dataset and it is not a competition submission.

## Run The Demo

From the repository root:

```bash
python tools/backtester/run_backtest.py --strategy examples/demo_mean_reversion_strategy.py --data-dir examples/sample_data --out-dir examples/demo_runs --separate-days
```

The command should produce a run archive and summary JSON under `examples/demo_runs/`.

## Files

| File | Purpose |
| --- | --- |
| `demo_mean_reversion_strategy.py` | Minimal stateful `Trader` implementation with rolling fair-value logic. |
| `sample_data/prices_round_0_day_0.csv` | Synthetic order-book snapshots in the same semicolon-delimited shape used by the backtester. |
| `sample_data/trades_round_0_day_0.csv` | Synthetic public trades used by passive-fill modes. |

The real competition strategies live in `strategies/`; this folder exists only to make the infrastructure easy to verify publicly.
