# Sanitization Notes

The original project folder contained thousands of generated files: strategy variants, run archives, screenshots, cache files, logs, third-party research repositories, spreadsheets and temporary outputs.

For this public portfolio repository:

- Selected files were copied into a clean repository structure.
- Rough scratch filenames were replaced with descriptive names.
- Generated artifacts and binary data were excluded.
- Local machine paths were removed from copied research scripts.
- Larger live strategy files were kept close to the original where practical, while Round 1 and Round 2 were represented by cleaned public files that preserve the important decision logic without carrying over private scratch comments or local-only diagnostics.

Original source mapping:

| Repository path | Original source |
| --- | --- |
| `strategies/round1_osmium_pepper_dynamic_strategy.py` | Clean public rewrite based on `Prosperity 4/R1/R1Results/R1Submission.py` |
| `strategies/round2_no_algo_qualification_risk_control.py` | Clean public representation of the deliberate no-algo Round 2 submission |
| `strategies/round3_options_smile_strategy.py` | `Prosperity 4/R3/VelvetPCAInsightTester.py` |
| `strategies/round4_options_hydrogel_strategy.py` | `Prosperity 4/R4/SlingBlade.py` |
| `strategies/round5_dynamic_multi_asset_market_maker.py` | `Prosperity 4/R5/ColdSteel.py` |
| `research/pca_price_research.py` | `Prosperity 4/Backtester/pca_price_research.py` |
| `research/options_volatility_research.py` | `Prosperity 4/Backtester/velvet_options_research.py` |
| `research/hydrogel_signal_research.py` | `Prosperity 4/Backtester/hydrogel_signal_research.py` |
| `research/round5_parameter_optimizer.py` | `Prosperity 4/R5/r5_optimizer.py` |
| `research/round5_decision_report.py` | `Prosperity 4/R5/r5_10k_decision_report.py` |
| `research/manual_trading_decision_model.py` | `Prosperity 4/R3/manual_round3_decision_model.py` |
| `research/manual_population_simulation.py` | `Prosperity 4/R3/manual_round3_population_sim.py` |
| `tools/backtester/run_backtest.py` | `Prosperity 4/Backtester/run_backtest.py` |
| `tools/backtester/datamodel.py` | `Prosperity 4/Backtester/datamodel.py` |
| `tools/visualizer/prosperity_visualizer.py` | `Prosperity 4/Visualiser/dashboard/main.py` |
