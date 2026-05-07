# IMC Prosperity 4 Trading Portfolio

Selected strategy, research and tooling files from my IMC Prosperity 4 competition work.

I was the team captain and designed the algorithmic and manual strategy stack represented here. Final results were pending when this repository was first created.

This repository is intentionally curated: it keeps the strongest strategy and research work, with clean filenames and without the generated run archives, logs, caches, screenshots, spreadsheets or third-party research copies from the original working folder.

## Highlights

- Dynamic, model-led strategies rather than brittle hardcoded historical price anchors.
- Options pricing, implied volatility estimation, volatility-smile modelling and residual filters.
- Inventory-aware passive and active execution.
- Custom backtester for market replay and fill approximation.
- Desktop visualizer for PnL, fills, quotes, positions, order-book state and strategy comparison.
- Manual trading decision models using scenario and population-level reasoning.

## Repository Structure

```text
strategies/       Selected final/substantive strategy files.
research/         Research, optimization and manual-trading analysis scripts.
tools/backtester/ Custom market replay and execution approximation tool.
tools/visualizer/ Desktop visualizer for run review and diagnostics.
docs/             Notes on strategy families and sanitization.
```

## Strategy Files

| File | Focus |
| --- | --- |
| `strategies/round3_options_smile_strategy.py` | Black-Scholes pricing, implied volatility, smile fitting, residual filters, Greeks and inventory controls. |
| `strategies/round4_options_hydrogel_strategy.py` | Expanded options and hydrogel strategy with passive/active execution, signal filtering and risk controls. |
| `strategies/round5_dynamic_multi_asset_market_maker.py` | Dynamic multi-asset market maker using rolling fair values, warmup regimes, product-level risk pruning and inventory-aware quoting. |

## Research Files

| File | Focus |
| --- | --- |
| `research/options_volatility_research.py` | Options and volatility research. |
| `research/pca_price_research.py` | PCA-style price research. |
| `research/hydrogel_signal_research.py` | Signal research for hydrogel-style products. |
| `research/round5_parameter_optimizer.py` | Parameter search and optimizer workflow. |
| `research/round5_decision_report.py` | Decision/reporting support for round 5 strategy selection. |
| `research/manual_trading_decision_model.py` | Manual trading decision model. |
| `research/manual_population_simulation.py` | Manual trading population simulation. |

## Tools

- `tools/backtester/run_backtest.py`: replays historical Prosperity data against a strategy file defining a `Trader` class.
- `tools/visualizer/prosperity_visualizer.py`: PySide6/PyQtGraph desktop dashboard for inspecting runs.

Historical CSVs and generated output folders are excluded from this first public version.
