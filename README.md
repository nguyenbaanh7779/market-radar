# market-radar

AI agent for Vietnamese stock market signal analysis, price-direction
forecasting, and paper trading. Research project for DX6000 (MSc Data
Science, SoICT, Hanoi University of Science and Technology), 2026-11 to
2027-01.

## Overview

Every trading day the agent:

1. **analyses signals** (Module 1) — VNINDEX trend, volatility and
   breadth, sector rotation against VNINDEX, technical flags per stock,
   and the status of your own holdings;
2. **forecasts direction** (Module 2, the focus) — UP / DOWN / SIDEWAY
   over 1 and 5 sessions (±0.2% band, Arena's scoring rule) for VNINDEX,
   VN30, a bank basket and about 75 stocks, with probabilities and the
   features that drove them; models are validated walk-forward with
   purging and an embargo and tested against baselines;
3. **paper-trades** (Module 3) — top-5 stocks by P(UP) over 5 sessions,
   rebalanced every 5 sessions, 100-share lots, T+2, fees and tax, a 7%
   stop-loss, filled at the next session's close, compared with
   buy-and-hold of VN30;

then sends a short newsletter and commits every forecast to the `data`
branch before its outcome is known, so the forward test can be audited.
It never trades real money.

```
            Arena EOD bars (or vnstock v6)  ──>  data/raw (Parquet, DuckDB)
                           │
         ┌─────────────────┼──────────────────┐
         ▼                 ▼                  ▼
 1. Signals ──features──> 2. Forecaster ──P(UP)──> 3. Paper trading
         │                 │                  │
         └────────> newsletter (Telegram) <───┘     state -> `data` branch
```

Research questions, data decisions and evaluation protocol:
[docs/strategy/README.md](docs/strategy/README.md).

## Repository structure

```
config/          settings, universe (VN30, banks, 8 sectors), holidays, portfolio template
src/market_radar/
  data/          sources (Arena, vnstock v6), Parquet store, update, quality checks
  signals/       Module 1: indicators, market state, sector rotation, ticker flags, portfolio
  forecaster/    Module 2: labels, features, models, walk-forward, evaluation, agent interface
  trader/        Module 3: broker (lots, T+2, costs), strategy, backtest, metrics
  report/        newsletter template, Telegram delivery
  dataset.py     bars -> baskets, signals, features, labels
  forward.py     forward-test logs and paper account
  pipeline.py    update / evaluate / backtest / daily
  cli.py         `market-radar` command
tests/           pytest on synthetic data (no network)
docs/            strategy/ (research design), architecture/ (system, data dictionary), guide/ (setup)
.github/         ci.yml (lint + tests), daily.yml (05:30 ICT run)
```

`data/` and `state/` are generated and gitignored; the forward-test
state lives on the `data` branch.

## Getting started

Python ≥ 3.12 (setup details, including uv on macOS, in
[docs/guide/README.md](docs/guide/README.md)):

```bash
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -r requirements.txt && uv pip install -e . --no-deps
pytest -q
```

## Usage

```bash
market-radar update      # download daily bars from the Arena API (no key needed)
market-radar check       # data-quality report
market-radar signals     # market, sector and ticker signals of the latest session
market-radar evaluate    # walk-forward evaluation of all models, DM tests
market-radar backtest    # paper trading on the out-of-sample forecasts vs VN30
market-radar daily --state-dir state --send   # the daily run
```

Settings live in `config/settings.yaml`; outputs are described in
[docs/architecture/data_dictionary.md](docs/architecture/data_dictionary.md).

## Data

Bars come from the public API of [Arena](https://ckai.vn) (no key, daily
OHLC since 2019, no volume, published around 04:30 ICT the next morning),
which is also what Arena scores predictions against. vnstock v6 with a
broker API key is supported as an optional source that adds volume.

## Status

Walking skeleton in place: all three modules run end to end on real
data, with tests, CI and the daily job. First baseline: the logistic
model beats both baselines on 1-session log loss (DM p = 0.002), the
5-session models do not yet, and the trading rule trails VN30 —
details in [docs/strategy/README.md](docs/strategy/README.md) Section
12. Next steps and the week-by-week plan: [TODO.md](TODO.md).

Research prototype for a course project — **not investment advice**.

## License

MIT, see [LICENSE](LICENSE).
