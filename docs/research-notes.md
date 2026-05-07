# Research Notes

This repository is built around one modelling principle: avoid brittle absolute-price rules where a live, adaptive estimate can do the job.

## Trading Strategy Philosophy

The main strategies use rolling fair values, product-specific risk controls and inventory-aware quoting. The goal was not to discover one magic historical price level, but to keep recalculating fair value from current book state and recent history, then only trade when the model edge justified taking inventory.

Key design choices:

- Use live order-book snapshots to form mid, spread and wall-mid views.
- Maintain rolling fair values through EMA-style estimates and product-specific windows.
- Gate orders by edge, liquidity, position limits and stale-signal checks.
- Scale quoting by inventory so the strategy naturally de-risks when it is already long or short.
- Prune products where replay showed weak PnL, excessive drawdown or poor fill quality.

## Options And Volatility Work

The options work focused on model value rather than directional guessing. The research scripts support Black-Scholes-style pricing, implied volatility estimation, volatility-smile fitting and residual filters across strikes.

The trading logic then combines:

- Theoretical option value.
- Implied-volatility and smile residual signals.
- Liquidity and position constraints.
- Delta-aware inventory pressure.
- Stale-signal avoidance.

## Manual Trading Work

Manual rounds were treated as quantitative decision problems. Some had explicit payoff formulas; others required modelling what the population of other teams would do. The public notes in `docs/manual-trading.md` summarize each round without publishing the original spreadsheets.

The most important recurring idea was distribution-aware decision making: maximize expected value only when the lower tail and crowding risk are acceptable.

## Infrastructure

The custom backtester and visualizer were built to shorten the research loop:

1. Replay historical market data.
2. Generate strategy orders from a `Trader` class.
3. Approximate active and passive fills.
4. Track PnL, positions, fills and risk statistics.
5. Inspect the resulting run in the visualizer.
6. Refine parameters and repeat.

The tiny example under `examples/` exists so this loop can be verified without publishing private competition CSVs.
