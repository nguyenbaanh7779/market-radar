# CHANGELOG

## Unreleased

### Features

- Add the `market_radar` package skeleton (src layout, `market-radar` CLI entry point, pinned `requirements.txt`, ruff and pytest config), typed settings loaded from `config/` (`settings.yaml`, `universe.yaml` with VN30, banks and 8 sectors, `holidays.yaml`, `portfolio.example.yaml`), `.env.example` for local secrets, and a trading calendar that projects future sessions
- Add the data layer: daily bars from the keyless Arena (ckai.vn) API by default or vnstock v6 with a broker key, one Parquet file per symbol with incremental updates, DuckDB loading, and quality checks (gaps, inconsistent OHLC, moves beyond the exchange price limit, cross-source differences)
- Add Module 1 signals: pandas-only indicators, market state (VNINDEX trend, volatility percentile, breadth, liquidity), equal-weight sector baskets with an RRG-style rotation view, strong/caution flags per stock and the status of the user's holdings
- Add Module 2, the direction forecaster: UP/DOWN/SIDEWAY labels over 1 and 5 sessions with Arena's ±0.2% band (voided across suspect jumps), point-in-time features, `majority`, `momentum`, `logistic` and `gbdt` (LightGBM with TreeSHAP drivers; a HistGB fallback is logged as `gbdt-histgb`) behind one `ForecastAgent` interface, purged and embargoed walk-forward validation, and a Diebold–Mariano test on daily log loss
- Add Module 3, paper trading: a cash account with 100-share lots, T+2, 0.15% fees and 0.1% selling tax; top-5 stocks by P(UP) over 5 sessions weighted by P(UP) − P(DOWN), rebalanced every 5 sessions with a daily 7% stop-loss, filled at the next close; a backtest against buy-and-hold of VN30
- Add the daily pipeline and CLI (`update`, `check`, `signals`, `evaluate`, `backtest`, `daily`): forecasts of every model logged before their outcome, resolution of past forecasts, a forward paper account, and a newsletter sent to Telegram — in Vietnamese by default (`report.language`, English template kept) — with idempotent CSV logs and the personal portfolio kept out of saved copies
- Add GitHub Actions: `ci.yml` (ruff and pytest on Python 3.12) and `daily.yml` (05:30 ICT on weekdays, retries while bars are unpublished, state committed to the orphan `data` branch)
- Add the documentation: `docs/strategy/README.md` (research design, changes from the proposal, baseline results), `docs/architecture/` (system overview and data dictionary with a source log), `docs/guide/README.md` (setup incl. libomp for LightGBM on macOS, secrets, data branch, optional vnstock v6), the 13-week `TODO.md` (incl. a holdout period and a binary-label variant to evaluate) and the project README
