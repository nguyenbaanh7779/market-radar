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

First download: 2026-11-17. Of the 78 symbols requested since
2026-11-22, Arena has 76; MCH and VPL have no bars.

Arena's prices are back-adjusted for most dividends but not all, and it
repeats the previous bar on sessions without trading. The data-quality rules
are in `docs/strategy/README.md` Section 5.3, and the evidence is in
`notebooks/01_data_understanding.ipynb`.

### 1.1 Exchange transfers (`exchange_history` in `config/universe.yaml`)

The first HOSE session trades with a ±20% limit. IDC moved from UPCoM to HNX
and was found by the high/low check (`range_breaches`).

| Stock | Earlier exchange | Last session there | First HOSE session | Source |
|---|---|---|---|---|
| IDC | UPCoM | 2019-11-29 | 2019-12-10 (HNX, not HOSE) | [VnEconomy](https://vneconomy.vn/idc-sap-len-san-hnx-voi-gia-18500-dong-co-phieu.htm), [Vietstock](https://en.vietstock.vn/2019/12/hnx-approves-listing-of-idico-965-374775.htm) |
| GVR | UPCoM | 2020-03-06 | 2020-03-17 | [VietnamPlus](https://en.vietnamplus.vn/rubber-group-moves-listing-from-upcom-to-hose/170227.vnp), [Nhà đầu tư](https://nhadautu.vn/4-ty-co-phieu-gvr-se-dung-giao-dich-tren-san-upcom-d34453.html) |
| DGC | HNX | 2020-07-17 | 2020-07-28 | [Thị trường Tài chính Tiền tệ](https://thitruongtaichinhtiente.vn/ngay-28-7-co-phieu-aph-va-dgc-chao-san-hose-28418.html) |
| BCM | UPCoM | 2020-08-19 | 2020-08-31 | [Tin nhanh chứng khoán](https://www.tinnhanhchungkhoan.vn/ngay-318-becamex-bcm-se-chao-san-hose-voi-gia-tham-chieu-28000-dong-post248477.html) |
| LPB | UPCoM | 2020-10-23 | 2020-11-09 | [VietnamPlus](https://www.vietnamplus.vn/co-phieu-lienvietpostbank-se-bat-dau-giao-dich-tren-hose-tu-911-post674038.vnp) |
| VIB | UPCoM | 2020-10-29 | 2020-11-10 | [Thị trường Tài chính Tiền tệ](https://thitruongtaichinhtiente.vn/gan-1-ty-co-phieu-vib-chinh-thuc-niem-yet-tren-san-hose-32534.html) |
| ACB | HNX | 2020-12-01 | 2020-12-09 | [Thời báo Tài chính](https://thoibaotaichinhvietnam.vn/co-phieu-acb-len-san-hose-vao-ngay-912-31876.html) |
| VCG | HNX | 2020-12-21 | 2020-12-29 | [Vietnam Finance](https://vietnamfinance.vn/co-phieu-vcg-tang-gan-8-trong-ngay-giao-dich-dau-tien-tai-hose-d59540.html) |
| VIX | HNX | 2020-12-28 | 2021-01-08 | [Vietnam Finance](https://vietnamfinance.vn/vix-chuyen-sang-giao-dich-tren-hose-vao-ngay-81-d59685.html) |
| SHB | HNX | 2021-10-05 | 2021-10-11 | [Thị trường Tài chính Tiền tệ](https://thitruongtaichinhtiente.vn/tu-ngay-11-10-co-phieu-shb-chinh-thuc-giao-dich-tren-hose-37217.html) |
| HHV | UPCoM | 2022-01-06 | 2022-01-20 | [Thời báo Tài chính](https://thoibaotaichinhvietnam.vn/deo-ca-chinh-thuc-niem-yet-hon-267-trieu-co-phieu-tren-hose-99142.html) |
| CTR | UPCoM | 2022-02-14 | 2022-02-23 | [VnBusiness](https://vnbusiness.vn/ctr-chinh-thuc-don-nha-ve-hose-vao-ngay-232.html) |
| NAB | UPCoM | 2024-02-28 | 2024-03-08 | [VnEconomy](https://vneconomy.vn/ngay-8-3-toi-nam-a-bank-len-san-hose-voi-gia-15-900-dong-co-phieu.htm) |
| BSR | UPCoM | 2025-01-06 | 2025-01-17 | [Tạp chí Công Thương](https://tapchicongthuong.vn/loc-hoa-dau-binh-son--bsr-chot-ngay--chuyen-nha--va-gia-niem-yet-tren-hose-131374.htm), [VSD](https://vsd.vn/en/ad/178213) |

Every "last session" is also the last distinct bar in the Arena series
before the copies. Coming next: all HNX stocks move to HOSE on 2026-12-28,
with 2026-12-23 as the last HNX session
([Báo Đầu tư](https://baodautu.vn/chot-lich-chuyen-co-phieu-niem-yet-tu-hnx-sang-hose-d710687.html)).

### 1.2 VN30 constituents (`vn30` in `config/universe.yaml`)

| Effective | Out | In | Source |
|---|---|---|---|
| 2025-08 | BVH | DGC | [Vietnam Finance](https://vietnamfinance.vn/bvh-mat-suat-vn30-lo-ro-diem-yeu-thanh-khoan-kho-go-d129819.html) |
| 2026-02-02 | BCM | VPL | [Vietnam Finance](https://vietnamfinance.vn/vn30-co-cau-danh-muc-bcm-bi-loai-ho-nha-vin-them-mot-suat-d139176.html) |
| 2026-05-13 | DGC | BSR | [Vietnam Finance](https://vietnamfinance.vn/dgc-bi-loai-khoi-ro-vn30-bsr-duoc-them-vao-thay-the-d144504.html) |
| 2026-08-03 | PLX, TPB | MCH, TCX | [Vietstock](https://vietstock.vn/2026/07/mch-tcx-vao-ro-vn30-3358-1466674.htm) |
| 2026-11-16 | — | — | Weights only ([ACBS](https://acbs.com.vn/acbsmedia/2026/10/HOSE_Cap-nhat-thay-doi-quy-tac-chi-so.pdf)) |

### 1.3 Corporate actions checked against the bars

| Bar | Move | Event | Source |
|---|---|---|---|
| ACB 2021-06-10 | −19.7% | 25% stock dividend, record date 2021-06-11 | [VnEconomy](https://vneconomy.vn/acb-chot-danh-sach-phat-hanh-co-phieu-tra-co-tuc-25.htm) |
| VND 2021-06-10 | −34.6% | 1:1 rights issue at 14,500 VND | [Báo Đầu tư](https://baodautu.vn/vndirect-2145-trieu-co-phieu-vnd-moi-sap-ve-tai-khoan-nha-dau-tu-d149230.html) |
| TCX 2026-09-16 | −17.6% | 5:1 stock dividend, ex-date 2026-09-17 in the press | [Báo Pháp luật](https://doanhnhan.baophapluat.vn/chung-khoan-ky-thuong-tcx-chia-co-tuc-ty-le-5-1-von-dieu-le-sap-vuot-moc-33-000-ty-dong.html) |
| FPT 2026-09-18 | −12.3% | 10:1 bonus shares, record date 2026-09-22 | [CafeF](https://cafef.vn/fpt-chot-ngay-phat-hanh-hon-171-trieu-co-phieu-thuong-1882609102017279.chn) |
| PNJ 2026-07 | 63.0 → 31.0 | Genuine sell-off (P-Lab case), nine limit-down sessions | [Tuổi Trẻ](https://tuoitre.vn/co-phieu-pnj-lai-giam-san-nhom-dau-khi-lao-doc-100260721151113326.htm), [Dân trí](https://dantri.com.vn/kinh-doanh/co-phieu-pnj-chua-duoc-cuu-20260707154829299.htm) |

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
| labels | `fwd_ret_<h>` | 100 · (close *h* sessions later / close − 1); NaN when the window spans a move beyond the price limit of the day or a copied bar |
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
| `universe.yaml` | Indices, baskets, VN30, banks, sectors, non-HOSE exchanges, `exchange_history` (earlier listings), price limits and the first-session limit |
| `holidays.yaml` | Upcoming exchange holidays (for projected sessions) |
| `portfolio.example.yaml` | Template of the personal holdings file (`config/portfolio.yaml`, gitignored) |
