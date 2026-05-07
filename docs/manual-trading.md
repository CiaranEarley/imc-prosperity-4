# Manual Trading Notes

Public-safe summary of the manual trading work from IMC Prosperity 4. The original spreadsheets are intentionally excluded from this repository, but each round is represented here with the modelling approach and final decision logic.

## Round Summary

| Round | Challenge type | Modelled approach | Decision / output |
| --- | --- | --- | --- |
| 1 | Auction clearing-price optimisation | Simulated how an added order changed clearing price, queue priority, fill quantity and guaranteed resale profit. | DRYLAND_FLAX: buy at 30, quantity 9,001, clearing price 29, profit 9,001. EMBER_MUSHROOM: buy at 17, quantity 19,001, clearing price 16, profit 74,103.9. |
| 2 | Manual allocation / risk decision | Modelled Research, Scale and Speed allocations against uninformed and informed population distributions. | This round was treated as a risk-controlled manual decision rather than an algorithmic trading build because qualification was already secured. Chosen allocation: Research 16%, Scale 47%, Speed 37%. The pure model-best allocation was Speed 43%, Scale 42%, Research 15%, but the chosen allocation favoured a lower-risk guaranteed-profit route. |
| 3 | Two-bid reserve-price problem | Built a reusable decision model for first/second bids, reserve buckets, population average of second bids and penalty-adjusted expected units. | Candidate bid pairs were tested across simulated population scenarios. Robust pairs included 750/835 and 755/840 in central scenarios; 760/850 performed best when the population overbid; 775/880 protected against very high population anchors. |
| 4 | Aether Crystal options portfolio | Simulated option portfolios using a zero-drift GBM, 251% annual volatility, discrete expiry steps and 100-path score distributions matching the challenge lens. | Preferred Choice 2 or 3 depending on risk appetite. Choice 2 had cleaner lower-tail behaviour; Choice 3 had higher EV while keeping a positive 5th percentile in validation. |
| 5 | News-driven commodity allocation | Converted qualitative news into direction, severity, confidence, expected price change, fee-adjusted cash and position sizing. | Allocated 71% of capital across the strongest positive and negative news trades, with expected return of about 10.25% in the workbook model. |

## Selected Details

### Round 2 Allocation Model

The workbook separated the crowd into uninformed actors, informed frontier actors and later informed actors. It then compared allocation choices against the resulting distribution. The final choice intentionally did not chase the highest displayed model PnL because the strategic objective was to preserve a strong, low-risk outcome after qualification was already secured.

### Round 3 Population Simulation

The public repository includes:

- `research/manual_trading_decision_model.py`
- `research/manual_population_simulation.py`

These scripts model reserve capture, penalty-adjusted second-bid value and population-level bid averages. The population simulation stress-tests candidate bid pairs across several behavioural regimes: joint optimizers, single-bid thinkers, overbid-anchored populations, broad/confused populations and high/low skew cases.

### Round 4 Options Work

The manual options model evaluated EV, loss frequency and lower-tail percentiles rather than EV alone. The main trade shape used short binary put exposure hedged with long put downside protection and smaller overlays. This was deliberately framed as a distribution problem because the official scoring sampled a limited number of paths.

### Round 5 News Allocation

The allocation model used capital, fees and expected price-change assumptions to rank trades. High-conviction examples included a supply-shock scarcity trade, a negative demand/tax-change trade, a smart-home demand-growth trade, a strong negative contamination trade and an index-inclusion demand trade.

## Sanitization

The source workbooks contain rough notes, challenge text, local-only context and binary spreadsheet logic. They remain out of the public repository. This document keeps the clean evidence: round coverage, modelling method and final decision logic.
