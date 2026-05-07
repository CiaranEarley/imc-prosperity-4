# Strategy Summary

## Dynamic Multi-Asset Market Making

Represented by `strategies/round5_dynamic_multi_asset_market_maker.py`.

The round 5 strategy uses product-level configuration, rolling fair values, warmup regimes and inventory-aware quote placement. The aim was to avoid brittle absolute price anchors and instead let live book state and rolling estimates drive bid/ask placement.

Core ideas:

- EMA-style fair-value estimation across product families.
- Product-specific spread, edge, size and soft-limit controls.
- Passive quoting with selective active overlays.
- Warmup logic to reduce early-regime overfitting.
- Position and drawdown-aware pruning of product configurations.

## Options And Volatility Modelling

Represented by `strategies/round3_options_smile_strategy.py`, `strategies/round4_options_hydrogel_strategy.py` and `research/options_volatility_research.py`.

The options stack models option fair value through Black-Scholes-style pricing, implied volatility estimation and volatility-smile residuals. Trading decisions combine model edge, liquidity, residual filters and position limits.

Core ideas:

- Black-Scholes call pricing.
- Implied volatility estimation.
- Cross-strike volatility smile fitting.
- Residual z-score filters.
- Greeks and delta-aware inventory skew.
- IV carry and stale-signal avoidance.
- Public-flow features where useful.

## Manual Trading Research

Represented by `research/manual_trading_decision_model.py` and `research/manual_population_simulation.py`.

Manual trading work used technical valuation and decision-distribution reasoning to model how other participants were likely to act under payoff uncertainty.

Core ideas:

- Scenario analysis under incomplete information.
- Population-level decision simulation.
- Regret-style reasoning.
- Payoff asymmetry and crowd-behaviour modelling.

## Research Infrastructure

Represented by `tools/backtester/run_backtest.py` and `tools/visualizer/prosperity_visualizer.py`.

The backtester and visualizer supported a faster research loop:

- Replay historical market data.
- Approximate active/passive fills.
- Track PnL, positions and fills.
- Compare variants and parameter sweeps.
- Inspect own quotes against market state.
