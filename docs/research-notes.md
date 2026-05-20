# Research Notes

This repository is built around one modelling principle:

> Prefer adaptive fair-value estimation over brittle absolute-price rules.

## Pre-Competition Positioning

Before Prosperity 4 began, I reviewed the previous year's leaderboard and looked at country representation around the top 1-2% of the field. Singapore looked underrepresented relative to its status as a global trading hub, so I chose to represent Singapore rather than simply defaulting to my home country.

The idea was to benchmark against a sophisticated quant-finance region while still having a realistic chance of ranking highly within the country. The outcome was more competitive than expected because Singapore had a stronger field this year, but we still finished 7th in Singapore.

## Dynamic Strategy Philosophy

The trading strategy stack was designed to keep recalculating its view of fair value during the run.

Key design choices:

- Use live order-book snapshots to form mid, spread, wall-mid and imbalance views.
- Maintain rolling fair values through EMA-style estimates and product-specific windows.
- Gate orders by edge, liquidity, stale signals and position limits.
- Scale quoting by inventory so the strategy naturally de-risks when already long or short.
- Prune products where replay showed weak PnL, excessive drawdown or poor fill quality.
- Avoid fixed-price hardcoding when a live estimate could do the job.

This likely sacrificed some PnL against teams that optimized around fixed historical anchors. I considered that trade-off worthwhile because fixed anchors can fail badly after a regime change.

## Manual Trading Research

Manual rounds were treated as quantitative and game-theoretic modelling problems.

The recurring structure was:

1. Convert the challenge into a payoff model.
2. Identify the strategic component, usually the population distribution of other teams' decisions.
3. Separate likely teams into uninformed, semi-informed and well-informed groups.
4. Stress-test candidate decisions under alternative population assumptions.
5. Review the realized result after each round to refine the next model.

This mattered most in Rounds 2 and 3, where the optimal decision depended heavily on how other teams were likely to reason.

## Options And Volatility Work

The options work focused on model value rather than directional guessing. The research scripts support:

- Black-Scholes-style pricing;
- implied volatility estimation;
- volatility-smile fitting;
- leave-one-out residual checks;
- z-score filters;
- delta and vega diagnostics;
- public-flow and counterparty signal analysis where relevant.

Further post-round work showed that IV mispricing residuals were themselves mean-reverting. That was a strong research finding, but it was discovered too late to safely fold into the live Round 3 code.

The Round 3 result was hurt by a live execution issue: the research/log payload exceeded the official platform's character limit and interfered with quote submission. That post-round diagnosis directly improved the Round 4 production setup.

## Round 5 Search-Space Control

Round 5 introduced a large product universe. The main research risk was not failing to find patterns; it was finding too many attractive-looking patterns that were not robust.

The final process was:

- research broad families quickly;
- test candidate structures in replay;
- look for instability across days;
- discard relationships that only worked in-sample;
- keep simple market-making logic where it survived;
- add overlays only where the signal was still plausible after review.

That is why the final strategy is much simpler than the full private research workspace.

## Infrastructure

The custom backtester and visualizer were built to shorten the research loop:

1. Replay historical market data.
2. Generate strategy orders from a `Trader` class.
3. Approximate active and passive fills.
4. Track PnL, positions, fills and risk statistics.
5. Inspect the resulting run in the visualizer.
6. Refine parameters and repeat.

The tiny example under `examples/` exists so this loop can be verified without publishing private competition CSVs.
