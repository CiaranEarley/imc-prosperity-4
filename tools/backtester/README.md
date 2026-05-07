# Backtester

Custom Prosperity market replay and execution approximation tool.

The backtester replays historical Prosperity price and trade CSVs against a strategy file defining a `Trader` class. It reconstructs order books from the provided snapshots, calls the strategy at each timestamp and approximates fills from active and passive orders.

Key features:

- Historical day selection.
- Position and PnL tracking.
- Active and passive fill approximation modes.
- Run archives for downstream inspection.
- JSON summaries for comparing strategy variants.

## Public Demo

The repository includes a tiny synthetic market dataset and example strategy so the backtester can be exercised without private Prosperity CSVs:

```bash
python tools/backtester/run_backtest.py --strategy examples/demo_mean_reversion_strategy.py --data-dir examples/sample_data --out-dir examples/demo_runs --separate-days
```

The demo writes:

- A run archive containing activity logs, graph logs, positions, fills and the strategy snapshot.
- A compact summary JSON with profit, drawdown, Sharpe-style statistics, fill counts and final positions.

`examples/demo_runs/` is ignored by git because those outputs are generated artifacts.

## Input Format

Price files must be named like `prices_round_0_day_0.csv` and use semicolon delimiters. The matching trade file should use the same name with `prices_` replaced by `trades_`.

Required price columns:

```text
day;timestamp;product;bid_price_1;bid_volume_1;bid_price_2;bid_volume_2;bid_price_3;bid_volume_3;ask_price_1;ask_volume_1;ask_price_2;ask_volume_2;ask_price_3;ask_volume_3;mid_price;profit_and_loss
```

Required trade columns:

```text
timestamp;buyer;seller;symbol;currency;price;quantity
```

Generated run archives, smoke tests and large CSV files are intentionally excluded from this public portfolio repository.
