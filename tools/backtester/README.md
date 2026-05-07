# Backtester

Custom Prosperity market replay and execution approximation tool.

The backtester replays historical Prosperity price and trade CSVs against a strategy file defining a `Trader` class. It reconstructs order books from the provided snapshots, calls the strategy at each timestamp and approximates fills from active and passive orders.

Key features:

- Historical day selection.
- Position and PnL tracking.
- Active and passive fill approximation modes.
- Run archives for downstream inspection.
- JSON summaries for comparing strategy variants.

Generated run archives, smoke tests and large CSV files are intentionally excluded from this public portfolio repository.
