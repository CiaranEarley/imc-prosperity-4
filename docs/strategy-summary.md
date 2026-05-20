# Strategy Summary

This repository presents a public-safe version of my IMC Prosperity 4 algorithmic work. The common thread is dynamic modelling: estimate fair value from current market state and recent history, then trade only when model edge, liquidity and inventory constraints justify the risk.

## Why Dynamic Rather Than Hardcoded

Many Prosperity strategies can perform extremely well by identifying fixed historical anchors and optimizing aggressively around them. I deliberately avoided making fixed prices the core of the strategy stack.

The reason was risk. A hardcoded level can look brilliant in-sample and fail badly if the simulator changes regime. My preference was to accept lower PnL in exchange for logic that recalculated fair value during the run.

## Round 1: Osmium And Pepper Root

Represented by `strategies/round1_osmium_pepper_dynamic_strategy.py`.

Round 1 traded:

- `ASH_COATED_OSMIUM`
- `INTARIAN_PEPPER_ROOT`

### Ash-Coated Osmium

The Osmium model used:

- rolling short and long mid-price history;
- order-book mid and imbalance;
- z-score adjustment against recent history;
- a centre-pull term to avoid drifting too far from observed fair value;
- volatility-adaptive quote width and size;
- inventory-skewed passive orders;
- flattening logic when inventory became too large.

This behaved like an inventory-aware market maker with live fair-value estimation. The strategy could take attractive liquidity when the book was mispriced and then provide passive quotes when edge was sufficient.

### Intarian Pepper Root

Pepper Root behaved more like a drifting product. The model estimated:

- rolling regression slope;
- regression fit quality;
- drift regime;
- fair value implied by the current tick;
- book-level signals.

Execution combined a core target position with smaller overlays when the book offered attractive prices versus the live regression fair value.

## Round 2: No Algorithmic Trade

Represented by `strategies/round2_no_algo_qualification_risk_control.py`.

Round 2 was not a strategy failure or a missing file. It was a deliberate tournament decision.

After Round 1, the team was close enough to the 200k qualification threshold that the right decision was to avoid unnecessary algorithmic risk. The Round 2 strategy therefore returned no orders, while the manual submission locked in enough additional PnL to reach the finals.

## Round 3: Hydrogel, Options And Volatility Smile

Represented by `strategies/round3_options_smile_strategy.py`.

Round 3 introduced `HYDROGEL_PACK`, `VELVETFRUIT_EXTRACT` and a strip of call options. The public strategy file focuses on the options and Velvetfruit stack; the private competition stack also included a Hydrogel sleeve with structural lower/upper levels, tiered inventory targets and live fair-value gating.

The options strategy used:

- Black-Scholes-style call valuation;
- implied volatility estimation;
- weighted quadratic volatility-smile fitting;
- leave-one-out fair-value checks;
- residual z-score filters;
- IV carry signals;
- delta-aware inventory skew;
- passive market making where spreads and fair values justified it;
- microstructure scalp logic on selected strikes.

Further post-round research showed that option IV mispricing residuals were themselves mean-reverting. The strategy already had residual diagnostics, but the fully developed residual mean-reversion trade arrived too late to add safely into the live Round 3 submission.

The strategy was hurt live by a production-style issue: research/log payloads exceeded the official character limit, which stopped quotes from reaching the platform after a point. That diagnosis materially shaped the Round 4 cleanup.

## Round 4: Hydrogel And Expanded Options

Represented by `strategies/round4_options_hydrogel_strategy.py`.

Round 4 kept the options stack and added `HYDROGEL_PACK`.

Hydrogel logic included:

- adaptive lower/upper levels around a rolling centre;
- tiered inventory targets at extremes;
- passive quoting near model value;
- active sweeping only when edge and target inventory justified it;
- recycling and trimming logic after retracements;
- named-counterparty/public-flow features where they survived testing.

The options strategy also became more production-safe after Round 3:

- reduced logging risk;
- stronger gating around stale signals;
- public-flow fade features;
- Mark/counterparty signal handling;
- underlying mean-reversion and call-bias overlays;
- continued residual and IV-based option execution.

The counterparty work was exploratory. `Mark 38` was tested as a Hydrogel bias near useful price regions, while selected option and underlying Marks were tested as call-bias signals. These signals were not strong enough to drive the strategy alone, so they were kept as small overlays behind price, edge and inventory controls.

## Round 5: Dynamic Multi-Asset Market Maker

Represented by `strategies/round5_dynamic_multi_asset_market_maker.py`.

Round 5 expanded the tradable universe dramatically. The final strategy deliberately avoided overcomplicated cross-family structures unless they survived validation.

The production stack used:

- rolling EMA fair values across multiple windows;
- product-level modes: `fair`, `touch` and `off`;
- warmup regimes before long-window estimates were trusted;
- soft and hard position limits;
- inventory-scaled sizing;
- trend filters on selected product families;
- active overlays only where the signal justified taking liquidity;
- product pruning after official replay and post-run diagnostics.

The result was a broad, controlled market-making strategy rather than a brittle map of exact historical prices.

## Research Infrastructure

Represented by:

- `tools/backtester/run_backtest.py`
- `tools/visualizer/prosperity_visualizer.py`
- `research/round5_parameter_optimizer.py`
- `research/round5_decision_report.py`

The tooling supported:

- market replay;
- fill approximation;
- PnL and inventory tracking;
- quote/fill visualization;
- product-level diagnostics;
- strategy comparison;
- parameter sweeps;
- post-round error analysis.

The visualizer and backtester will eventually have their own dedicated repositories. They remain referenced here because they were central to the actual research loop.
