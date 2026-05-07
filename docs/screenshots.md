# Screenshot Plan

The repo will look much stronger with a few targeted screenshots. The goal is to show the full research loop, not to decorate the README.

## Priority Screenshots

| Priority | Filename | Capture |
| --- | --- | --- |
| 1 | `docs/assets/screenshots/visualizer-overview.png` | Full visualizer dashboard with PnL, positions/fills and order-book/own-quote diagnostics visible. |
| 2 | `docs/assets/screenshots/backtester-run-summary.png` | Backtester run summary or comparison output showing replay, fills/PnL and strategy result metrics. |
| 3 | `docs/assets/screenshots/strategy-comparison.png` | Strategy/parameter comparison from optimizer or report output. |
| 4 | `docs/assets/screenshots/options-volatility-research.png` | Options-volatility diagnostic: smile fit, residuals, implied volatility or related plot. |

## Capture Rules

- Crop out Windows taskbar, local usernames, absolute local paths and unrelated personal files.
- Prefer 16:9 or wide screenshots; GitHub README images render best when they are not overly tall.
- Avoid screenshots of raw code as the main evidence. The code is already in the repository; screenshots should show research output or tooling.
- Use readable zoom levels. Tiny terminal text does not help.
- Do not include competition login pages, private account identifiers or anything from non-public sources.

## How The README Will Use Them

Once images are added, the README can include a compact evidence section:

```md
## Research Tooling Evidence

![Visualizer overview](docs/assets/screenshots/visualizer-overview.png)
![Backtester run summary](docs/assets/screenshots/backtester-run-summary.png)
![Options volatility research](docs/assets/screenshots/options-volatility-research.png)
```

Only add the image links once the files exist, so the public README does not show broken images.
