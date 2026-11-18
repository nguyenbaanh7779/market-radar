# Data Dictionary

Units: stock prices in **thousand VND** (as both Arena and vnstock quote
them), index levels in points, money in **VND**, returns as fractions
unless the name ends in `_pct`. Dates are trading sessions
(`YYYY-MM-DD`, Asia/Ho_Chi_Minh).

## 1. Source log

| Source | Endpoint / package | Access | Licence / terms | Notes |
|---|---|---|---|---|
| Arena (ckai.vn) | `GET https://ckai.vn/vi/api/eod/market-bars?symbol=&from=&to=&interval=1d` | Public, no key | Platform terms at ckai.vn; Arena is "not a securities company and gives no investment advice" | `source` field `flow_mdp`; newest first; `volume` null; full refresh around 04:30 ICT; history from 2019-01-02 (some stocks later) |
| vnstock v6 | `vnstock.Market(provider).equity(symbol).ohlcv(...)` / `.index(...)` | Package from `https://vnstocks.com/api/packages`; broker API key per provider | vnstocks.com licence and the provider's terms | Optional (`data.source: vnstock`); adds volume |

First download: 2026-11-17, 77 of 78 requested symbols (MCH has no Arena
bars).

## 2. Raw bars — `data/raw/bars/<SYMBOL>.parquet`

| Column | Type | Description |
|---|---|---|
| `symbol` | str | Ticker or index (`VNINDEX`, `VN30`) |
| `date` | datetime | Session |
| `open`, `high`, `low`, `close` | float | Prices (thousand VND; points for indices) |
| `volume` | float | Shares traded; NaN for Arena |
| `source` | str | `arena` or `vnstock` |
| `fetched_at` | str | UTC time of the download (ISO 8601) |

Derived in memory (not stored): the `BANKS` basket — equal-weight average
of the banks' daily returns, open/high/low from their average gaps to the
previous close, base 100 (`source = basket`).

## 3. Signals — `market_radar.signals`

### 3.1 Market state (per session)

| Column | Definition |
|---|---|
| `idx_close` | VNINDEX close |
| `idx_ret_1`, `idx_ret_5`, `idx_ret_20` | VNINDEX return over 1, 5, 20 sessions |
| `idx_dist_ma20`, `idx_dist_ma50` | close / MA − 1 |
| `idx_ma20_ma50` | MA20 / MA50 − 1 |
| `idx_vol_20` | Annualised standard deviation of 20 daily log returns |
| `idx_vol_pctile` | Share of the last 250 values of `idx_vol_20` at or below today's |
| `breadth_up` | Share of universe stocks with a positive daily return |
| `breadth_above_ma20` | Share of universe stocks above their MA20 |
| `liquidity_ratio` | Universe traded value / its average over the previous 20 sessions (NaN without volume) |
| `regime` | `uptrend` (close > MA20 > MA50), `downtrend` (close < MA20 < MA50), else `sideways` |
| `high_vol` | `idx_vol_pctile` ≥ 0.8 |

### 3.2 Sector rotation (per session and sector)

| Column | Definition |
|---|---|
| `rs_ratio` | 100 · rs / mean(rs, last 50 sessions), rs = sector basket / VNINDEX |
| `rs_momentum` | 100 · rs_ratio / rs_ratio 10 sessions earlier |
| `quadrant` | `leading` (≥100, ≥100), `weakening` (≥100, <100), `lagging` (<100, <100), `improving` (<100, ≥100) |
| `score`, `rank` | (rs_ratio − 100) + (rs_momentum − 100); rank 1 = highest score |

### 3.3 Ticker flags

`flag` ∈ {`strong`, `neutral`, `caution`} and `reasons` (text); rules in
`docs/strategy/README.md` Section 7.

## 4. Modelling panel — `market_radar.dataset.assemble`

One row per instrument (stocks, indices, BANKS) and session.

| Group | Columns | Definition |
|---|---|---|
| keys | `date`, `symbol` | Session and instrument |
| helpers | `close`, `sector` | Close used for labels; sector used to join rotation features (not model inputs) |
| returns | `ret_1` … `ret_20` | close / close *k* sessions earlier − 1 |
| trend | `dist_ma20`, `dist_ma50`, `ma20_ma50` | As for the index |
| oscillators | `rsi_14` | Wilder RSI, 0–100 |
| | `macd_hist_norm` | (MACD 12/26 − signal 9) / close |
| | `bb_pct_b` | (close − lower band) / (upper − lower), bands 20 ± 2σ |
| volatility | `vol_20` | Annualised 20-session volatility |
| | `atr_14_norm` | Wilder ATR(14) / close |
| | `range_1` | (high − low) / close |
| volume | `vol_ratio_20` | Volume / mean of the previous 20 sessions (dropped without volume) |
| relative | `rel_ret_5`, `rel_ret_20` | `ret_k` − VNINDEX `ret_k` |
| market | `idx_*`, `breadth_*`, `liquidity_ratio` | Section 3.1, same for every instrument on a session |
| sector | `sec_rs_ratio`, `sec_rs_momentum` | Section 3.2 for the instrument's sector (BANKS → banking; NaN for indices) |
| instrument | `is_index` | 1 for indices and baskets |
| labels | `fwd_ret_<h>` | 100 · (close *h* sessions later / close − 1); NaN when the window spans a move beyond the price limit |
| | `label_<h>` | `UP` > 0.2, `DOWN` < −0.2, else `SIDEWAY` |

## 5. Evaluation results — `data/results/`

| File | Content |
|---|---|
| `oos_predictions.parquet` | Walk-forward predictions: `date`, `symbol`, `horizon`, `model`, `fold`, `y_true`, `p_down`, `p_sideway`, `p_up`, `y_pred`, `correct`, `log_loss`, `brier` |
| `wf_metrics.csv` | Per horizon and model: `n`, `accuracy`, `balanced_accuracy`, `macro_f1`, `log_loss`, `brier`, class shares |
| `wf_folds.csv` | The same per fold |
| `wf_significance.csv` | Diebold–Mariano: `candidate`, `baseline`, `mean_diff`, `dm_stat`, `p_value`, `sessions` |
| `backtest_equity.csv` | Per session: `equity_vnd`, `cash_vnd`, `invested_vnd`, `positions`, `benchmark_vnd` |
| `backtest_trades.csv` | Fills (see `trades.csv` below) |
| `backtest_summary.csv` | Strategy and benchmark metrics |

## 6. Forward-test state — `state/` (the `data` branch in CI)

| File | Content |
|---|---|
| `predictions.csv` | `created_at_utc`, `asof_date` (session the features come from), `target_date` (projected session the forecast is about), `symbol`, `horizon`, `model`, `model_version` (`<model>-h<h>-<settings hash>`), `git_sha`, `p_down`, `p_sideway`, `p_up`, `label_pred`, `asof_close`, `explanation` |
| `resolved.csv` | Key columns plus `target_date` (realised *h*-th session), `label_true`, `fwd_ret_pct`, `correct`, `log_loss`, `resolved_at_utc` |
| `orders.csv` | `planned_at`, `session` (fill session), `symbol`, `side`, `quantity`, `reason` (`entry`, `add`, `exit`, `stop_loss`) |
| `trades.csv` | `session`, `symbol`, `side`, `quantity`, `price`, `value_vnd`, `fee_vnd`, `tax_vnd`, `reason` |
| `equity.csv` | `date`, `equity_vnd`, `cash_vnd`, `positions`, `benchmark_close` |
| `account.json` | Cash, lots (quantity, price, fill session), `started`, `last_session`, pending orders |
| `signals/<date>.json` | Market state, sector rotation and ticker flags of the session |
| `reports/<date>.md` | The newsletter in `report.language` (Vietnamese by default), without the personal portfolio section |

## 7. Configuration — `config/`

| File | Content |
|---|---|
| `settings.yaml` | Source, periods, schedule, labels, validation, models, signal thresholds, trading rules, report options |
| `universe.yaml` | Indices, baskets, VN30, banks, sectors, non-HOSE exchanges, price limits |
| `holidays.yaml` | Upcoming exchange holidays (for projected sessions) |
| `portfolio.example.yaml` | Template of the personal holdings file (`config/portfolio.yaml`, gitignored) |
