# Research Design

Source of truth for the DX6000 project *AI agent for signal analysis,
price-direction forecasting and paper trading on the Vietnamese stock
market*. It is based on the DX6000 proposal submitted on 2026-11-13 and
replaces it: everything the proposal planned is here, with the decisions
the code follows. When the code and this document disagree, fix one of
them in the same change.

| Item | Value |
|---|---|
| Course | DX6000 – Proposed research project, MSc Data Science, SoICT, HUST |
| Supervisor | Trần Việt Trung |
| Period | 2026-11-02 to 2027-01-31 (13 weeks) |
| Reference platform | Arena – [ckai.vn](https://ckai.vn) |
| Keywords | stock forecasting, machine learning, walk-forward validation, paper trading, AI agent |

### Changes from the proposal

| Proposal | Now | Why |
|---|---|---|
| Data through the Arena API or vnstock | Arena API by default; vnstock v6 optional (Section 5.1) | vnstock left PyPI; from generation 6 every Vietnamese equity source needs a broker API key |
| Liquidity and volume-spike signals | Available only with a volume source | Arena's bars have no volume |
| Agent runs after the close; newsletter in the evening | Run at 05:30 ICT; newsletter before the open (Section 3) | Arena publishes the bars of session D around 04:30 ICT on D+1 |
| Daily bars from 2023 | Downloaded from 2019; samples still start 2023-01-01 | Indicator warm-up (MA50, RRG) and an optional 2022 bear-market check |
| Banking group | Equal-weight `BANKS` basket as an instrument (Section 5.2) | Arena's `BANKING` instrument has no published definition |
| Paper trading at closing prices | Decide after the close of *t*, fill at the close of *t* + 1; rebalance every 5 sessions (Section 9.1) | No decision uses a price it could not see; daily rebalancing turned over the portfolio ~130× a year |
| Runs on GitHub Actions | Runs on the author's Mac via launchd (GitHub workflow kept, disabled) | Arena answers HTTP 403 to GitHub's cloud runners |
| Dashboard and email delivery | Planned (TODO.md); Telegram first | The walking skeleton came first so the forward test could start early |

## 1. Background

Individual investors make up most of the trading on the Vietnamese
market, yet most of them lack the time and tools to analyse it; decisions
often rest on intuition and scattered information. Machine-learning
studies of stock forecasting usually stop at a backtest (prone to
overfitting), keep forecasts apart from trading decisions and offer no
explanation, so they are hard to use in practice.

The project builds an agent for an individual investor with three
connected functions — **signal analysis → forecasting → paper trading** —
centred on a single forecasting agent. Arena (ckai.vn), a platform where
AI agents compete on market predictions and paper portfolios, is the
reference for how signals are organised and scored, and an optional
channel for independent verification.

## 2. Objectives and research questions

**Objective:** an agent that helps an individual investor understand the
market, forecasts price direction and verifies its signals through
simulated trading.

| Module | Specific objective | Research question | How it is measured |
|---|---|---|---|
| 1. Signal analysis | Summarise the market, sector money flow, per-stock signals and the user's portfolio into a short daily brief | **RQ1:** Does it help the user grasp the situation and draw usable insights in little time? | Daily self-log: reading time, usefulness score (1–5), insights acted on (TODO `feat/delivery-feedback`) |
| 2. Forecasting (focus) | Direction forecasts validated walk-forward, with calibrated probabilities and explanations; an architecture open to specialised agents | **RQ2:** Does it beat the baselines with statistical significance? **RQ3:** Which signal groups contribute most? | Out-of-sample log loss, Brier, accuracy, balanced accuracy, macro F1; Diebold–Mariano test against baselines; ablation by feature group |
| 3. Paper trading | Turn forecasts into a simulated strategy with costs and risk control | **RQ4:** Does it beat buy-and-hold of VN30 on return and risk? | Total return, CAGR, volatility, Sharpe, Sortino, maximum drawdown, turnover, costs |
| Verification | Compare the backtest with live running | **RQ5:** Are backtest results consistent with the forward test? | Same metrics on forward predictions versus the distribution of walk-forward folds |

## 3. Users and usage scenario

The primary user is the student — an individual investor with a day job
and no time to watch the price board or read many sources. Every trading
day the agent updates the data, analyses and forecasts on its own; the
user reads a short newsletter, opens the dashboard to go from the
overview to details, and decides alone. The user enters their own
holdings for analysis; **the agent never places real orders.**

Because Arena publishes the bars of session D around 04:30 ICT on D+1
(Section 5.1), the keyless setup runs at **05:30 ICT** and the newsletter
arrives before the 09:00 open. With a same-evening data source (vnstock
v6 with a broker key) the run can move to the evening, as the proposal
first described.

| Feature | What the user gets |
|---|---|
| Daily newsletter | Telegram (email later), in Vietnamese for Vietnamese readers (`report.language`, `en` also available): the market, sectors attracting money, stocks with strong signals, stocks to watch out for |
| Daily dashboard | Overview → sector → stock → portfolio (allocation, P&L against VN30, paper-trading record) — planned, TODO.md |
| Explanation and confidence | Drivers of each forecast (logistic contributions, TreeSHAP for LightGBM), probabilities, past hit rate |

Extending the tool to other people would require checking the Vietnamese
rules on securities investment advice.

## 4. Scope

| Aspect | Scope |
|---|---|
| Market | VNINDEX, VN30 (index and constituents), listed banks, representative stocks of 8 sectors (`config/universe.yaml`) |
| Data | End-of-day OHLC since 2019 (history for warm-up), samples from 2023-01-01, via the Arena API (default) or vnstock v6 |
| Forecasts | Direction UP / DOWN / SIDEWAY over 1 and 5 sessions |
| Paper trading | Simulated at closing prices with fees, tax, board lots and T+2 |
| Out of scope | Real money, intraday data, signals of external agents, news and financial statements (thesis stage) |

## 5. Data

### 5.1 Sources

| Source | Access | Content | Use |
|---|---|---|---|
| Arena `GET /vi/api/eod/market-bars` | Public, no key | Daily OHLC since 2019-01-02 for indices and stocks; prices in thousand VND; **no volume**; bars of session D appear around 04:30 ICT on D+1 | Default source; also the ground truth Arena scores against |
| vnstock v6 (`Market(<provider>).equity/index(...).ohlcv`) | Installed from vnstocks.com; needs the user's own broker API key (`ssi`, `dnse`, `tcbs`, `fhsc`) | Daily OHLCV, adjusted, thousand VND | Optional; adds volume and same-evening runs |

The proposal planned vnstock as a free source. vnstock left PyPI and, from
generation 6 (versions before it stop working on 2026-11-10), every
Vietnamese equity source needs a key issued by a securities company. The
keyless Arena API is therefore the default.

### 5.2 Universe

78 symbols are requested: VNINDEX, VN30 and 76 stocks. The stocks are the
30 VN30 constituents, the 20 listed banks and 8 sectors:
- banking, with all 20 banks;
- real estate, securities, materials, consumer, technology, energy and
  industrials, with 5–11 representatives each.

An equal-weight basket of the banks, **BANKS**, is built as an instrument.
It stands in for Arena's `BANKING` instrument, whose definition is not
published. Arena has bars for every symbol except MCH and VPL, so 77
instruments are forecast.

The VN30 list is the one in force since 2026-08-03. It was verified
on 2026-11-22 by chaining HOSE's review results:

| Effective | Out | In |
|---|---|---|
| 2025-08 | BVH | DGC |
| 2026-02-02 | BCM | VPL |
| 2026-05-13 | DGC | BSR |
| 2026-08-03 | PLX, TPB | MCH, TCX |
| 2026-11-16 | weights only | — |

Applying today's constituents to the whole history introduces
**survivorship bias**: stocks that left the large-cap group (BCM, DGC,
PLX, TPB…) are missing from the earlier years, so backtest results are
mildly optimistic. This is a threat to validity to state in the report.

### 5.3 Quality rules

`market-radar check` reports, per symbol:
- sessions missing against the VNINDEX calendar;
- duplicate dates;
- inconsistent OHLC;
- moves beyond the price limit of the day;
- highs or lows beyond the ceiling or floor of the day (reported only:
  labels use closes);
- bars copied from the previous session;
- volume coverage.

Findings from `notebooks/01_data_understanding.ipynb` (data to 2026-11-17):

- **Price limits follow the exchange of the day.** HOSE allows ±7%, HNX
  ±10% and UPCoM ±15%. Fourteen stocks changed exchange during the
  sample: 13 moved to HOSE, for example ACB from HNX in December 2020 and
  BSR from UPCoM in January 2025, and IDC moved from UPCoM to HNX in
  December 2019. `exchange_history` in `config/universe.yaml` records the last
  session on the earlier exchange, checked against the press. The first
  session on the new exchange allows ±20%. Checking each stock against its
  *current* exchange flagged 340 moves; the exchange of the day leaves 37.
- **Arena's prices are back-adjusted, but not completely.** For the median
  stock, 60% of closes before 2026 are off the HOSE price grid, while STB,
  which paid no dividend, sits on it throughout. Some ex-dates are still
  unadjusted:
  - the May–June 2021 wave of stock dividends and rights issues (ACB, HPG,
    NVL, VIB, VND, VCI…);
  - TCX and FPT in September 2026.

  A move beyond the limit therefore still marks a corporate action, and
  **labels whose window spans such a move are voided**. Events small enough
  to stay within the limit cannot be detected this way.
- **Copied bars.** Arena repeats the previous bar on sessions without
  trading, such as the days between two listings or illiquid UPCoM days.
  Such bars are 0.5% of all bars, and 82 since 2023. **Labels whose window
  contains a copied bar, or the first real bar after copies, are voided.**
  An unchanged close would otherwise be scored as a SIDEWAY session that
  never happened.
- **Genuine extreme moves stay.** PNJ fell from 63.0 to 31.0 in July 2026
  through nine limit-down sessions; the press confirms a real sell-off.
- Inconsistent OHLC rows are rare: 75 in total, mostly HHV in 2019–2020,
  and 8 on HNX stocks in May 2025. Labels use closes only, so they are
  kept.
- **Coming change:** all HNX stocks (SHS, MBS, PVS and IDC here) move to
  HOSE on 2026-12-28. The config is to be updated once their price limit
  is published.

### 5.4 Sample period

Bars are downloaded from 2019 and the modelling sample starts at
**2023-01-01**. Training from 2020 instead was tested on identical
walk-forward test blocks ending before the planned holdout (2026-06-01).
It lowered the logistic log loss at both horizons:

| h | Train from 2023 | Train from 2020 | DM, p |
|---|---|---|---|
| 1 | 0.998 | 0.995 | −1.71, 0.09 |
| 5 | 0.872 | 0.859 | −1.59, 0.11 |

The gain is not significant at 5%, so the start stays at 2023 and the 2020
variant is the first one to test in `feat/forecaster-v1`. From 2020 the
sample would add the COVID crash, the 2021 boom and the 2022 bust (VNINDEX
−40%), which a 2023 start never sees.

## 6. Labels

For instrument *i* at session *t* and horizon *h*:

    r(i, t, h) = close(i, t + h) / close(i, t) − 1
    label = UP if r > +θ;  DOWN if r < −θ;  SIDEWAY otherwise

with h ∈ {1, 5} sessions and θ = 0.2%. With h = 1 this is exactly Arena's
`direction_brier_v1` rule (`return_pct = (close_D − close_{D−1}) /
close_{D−1}`, default band 0.2%). Arena's direction leaderboards are
`VN30` 1D, `BANKING` 1D and `VNINDEX` 5D, all with a 0.2% band.

SIDEWAY is the minority class at this band. From 2023 it is:
- 14% of stock labels and 20% of index labels at h = 1;
- 5% and 7% at h = 5, so the 5-session problem is nearly binary.

65% of the stock SIDEWAY labels at h = 1 are an exactly unchanged close.
At 10–50 thousand VND one price tick is 0.1–0.5%, so the band mostly
captures "no move".

A band of 0.5% gives a more balanced problem (29% SIDEWAY at h = 1). It
would, however, stop matching Arena's rule and change the labels the
forward test logs. **θ stays at 0.2%.** A binary UP/DOWN variant is tested
in `feat/forecaster-v1`.

## 7. Module 1 – signal analysis

Transparent rules, no training. The output feeds both the newsletter and
Module 2's features.

| Layer | Signals |
|---|---|
| Market state | VNINDEX against MA20/MA50 (regime: uptrend / sideways / downtrend), 20-session volatility and its 250-session percentile, breadth (share of stocks up, share above MA20), liquidity against its 20-session average (needs volume) |
| Sector money flow | Equal-weight sector baskets; RRG-style RS-ratio = 100 · rs / mean(rs, 50) and RS-momentum = 100 · RS-ratio / RS-ratio 10 sessions ago, with rs = sector / VNINDEX; quadrant (leading, weakening, lagging, improving) and rank. A transparent approximation, not the proprietary JdK formulas |
| Per stock | RSI(14), MACD(12, 26, 9), Bollinger %B(20, 2), volume ratio, position against MA20/MA50 → `strong` (uptrend, MACD > 0, RSI 50–70) or `caution` (RSI ≥ 75, below MA50 with MACD < 0, or below the lower band) |
| Portfolio | Allocation by sector and concentration (HHI), P&L and VN30 return since a start date, top contributor, holdings with weak signals or in lagging/weakening sectors |

## 8. Module 2 – forecasting agent (focus)

### 8.1 Features

All point-in-time (a test checks that changing prices after *t* leaves
the features at *t* unchanged): lagged returns (1, 2, 3, 5, 10, 20),
trend (distance to MA20, MA50, MA20/MA50), oscillators (RSI, MACD
histogram / close, %B), volatility (realised, ATR / close, daily range),
volume ratio (when available), return relative to VNINDEX (5, 20),
market state (Module 1) and the sector's RS-ratio and RS-momentum
(Module 1), plus an index/basket flag. One panel model covers stocks,
indices and the BANKS basket.

### 8.2 Models

| Model | Role |
|---|---|
| `majority` | Baseline: class frequencies of the training window |
| `momentum` | Baseline: P(direction ahead given the direction of the past *h* sessions) |
| `logistic` | Multinomial logistic regression (median imputation, standardisation, C = 0.1); primary model of the skeleton |
| `gbdt` | LightGBM (300 trees, 15 leaves, ≥ 200 rows per leaf) |
| XGBoost, LSTM | Planned (`feat/forecaster-v1`); LSTM as a comparison only |

### 8.3 Validation

Expanding-window walk-forward from 2023-01-01: at least 250 training
sessions, 21-session test blocks, the last *h* training sessions purged
(their labels overlap the test block) plus a 5-session embargo (López de
Prado, 2018). Every model is refitted on each fold.

Metrics: log loss and Brier score (probability quality), accuracy,
balanced accuracy and macro F1 (class imbalance). Significance: a
Diebold–Mariano test on the **daily average** loss difference between a
candidate and each baseline, with a Newey–West variance (lag *h*), so the
correlation between instruments on the same day does not inflate the
sample.

Planned: class-imbalance handling, probability calibration (isotonic or
Platt on an inner validation block), hyperparameter tuning inside the
walk-forward, SHAP summaries and ablation by feature group (RQ3).

### 8.4 Agent interface and extension

Every agent implements the same contract: input = data up to session
*t*; output = label, probabilities, explanation and a version string
(`ForecastAgent`). Specialised agents built later (technical, money flow,
fundamentals, per sector) and a combiner that weights them by market
regime plug into the same interface — the thesis direction.

## 9. Module 3 – paper trading

### 9.1 Rules

| Rule | Value |
|---|---|
| Capital | 100,000,000 VND |
| Signal | P(UP) of the 5-session forecast of the primary model (1-session forecasts do not fit T+2) |
| Selection | Top 5 stocks with P(UP) ≥ 0.40 and P(UP) > P(DOWN) |
| Weights | Proportional to P(UP) − P(DOWN), at most 30% per stock; the rest in cash |
| Rebalance | Every 5 sessions (the forecast horizon); between rebalances only stop-losses act |
| Exits | Stock no longer selected at a rebalance, or stop-loss at −7% from the average cost (checked after every close) |
| Execution | Decided after the close of *t*, filled at the close of *t + 1* (ATC order) — never at a price the decision could not see |
| Market rules | 100-share lots; T+2 (shares bought on *b* can be sold from *b + 2*); 0.15% fee per side; 0.1% selling tax; sale proceeds usable at once (simplification) |
| Benchmark | Buy-and-hold of the VN30 index |

### 9.2 Backtest

`market-radar backtest` replays the out-of-sample forecasts of the
walk-forward and reports return, CAGR, volatility, Sharpe and Sortino
(zero risk-free rate), maximum drawdown, Calmar, turnover and costs for
the strategy and the benchmark (RQ4). Cost and parameter sensitivity are
planned (`feat/paper-trading-v1`).

## 10. Forward test

### 10.1 Protocol

A launchd job on the author's Mac runs `market-radar daily` at 05:30 ICT on weekdays (GitHub Actions was the plan, but Arena refuses cloud servers):
update the bars, check the expected session has been published (else
retry for up to 90 minutes), compute the signals, refit every model on
all labels known at *t*, forecast every instrument for 1 and 5 sessions,
resolve older forecasts whose target session has closed, advance the
paper account, write the newsletter, and commit the state to the
**`data` branch**. Each commit timestamps the forecasts before their
outcome exists, which makes the forward test auditable (RQ5).

### 10.2 Records

`predictions.csv` (every model and horizon, probabilities, model version
and code commit), `resolved.csv`, `orders.csv`, `trades.csv`,
`equity.csv`, `account.json`, `signals/<date>.json`,
`reports/<date>.md` (without the personal portfolio). Field definitions:
[`docs/architecture/data_dictionary.md`](../architecture/data_dictionary.md).

### 10.3 Analysis (RQ5)

Compare forward metrics with the distribution of walk-forward fold
metrics for the same model and horizon (is the forward value inside the
fold range?), check the paper account against the backtest of the same
period, and report the number of sessions honestly: by 2027-01-29 a
forward test started in late November covers about 45 sessions.

### 10.4 Arena (optional)

Arena accepts direction predictions through `POST
/api/agents/:id/predictions` (API key, `Idempotency-Key`) until 08:05 ICT
of the target day, scores them 100/0, and ranks an agent once it has at
least 30 resolved predictions. To be ranked before the end of the
project, submission must start by mid-December.

## 11. Limitations and risks

- **Survivorship bias** in the universe (Section 5.2).
- **No volume** with the default source: liquidity and volume-spike
  signals are off until a keyed source is configured.
- **Partly adjusted prices:** Arena back-adjusts most dividends but not
  all. Small unadjusted events stay undetected, and a re-download can
  rewrite history (Section 5.3).
- **Data-source risk:** Arena's API is public but undocumented in parts
  and could change; vnstock needs a broker key; GitHub-hosted runners may
  be blocked by some Vietnamese sources.
- **Short forward test** (Section 10.3), and one market regime in it.
- **Not investment advice;** sharing the tool beyond the author needs a
  check of the rules on securities investment advice.

## 12. Baseline results of the skeleton (2026-11-22)

`market-radar evaluate` and `backtest` on Arena data, with the default
settings of this document. These numbers are the starting point the
planned work must beat, not results for the report.

They were first run on 2026-11-17, and re-run on 2026-11-22 after the
data-understanding changes:
- price limits by period;
- copied bars voided;
- BVH replaced by VPL in VN30.

The numbers barely moved. Accuracy at h = 1 was 0.447 against 0.419
before, with p = 0.002.

Walk-forward 2024-01 to 2026-11 (34 folds per horizon, 77 instruments):

| h | Model | n | Accuracy | Balanced accuracy | Log loss | Brier |
|---|---|---|---|---|---|---|
| 1 | majority | 53,848 | 0.420 | 0.333 | 1.004 | 0.613 |
| 1 | momentum | 53,848 | 0.418 | 0.332 | 1.004 | 0.613 |
| 1 | logistic | 53,848 | 0.447 | 0.349 | **0.998** | **0.610** |
| 1 | gbdt | 53,848 | 0.446 | 0.349 | 1.023 | 0.629 |
| 5 | majority | 53,022 | 0.476 | 0.333 | **0.857** | **0.548** |
| 5 | momentum | 53,022 | 0.476 | 0.333 | 0.857 | 0.548 |
| 5 | logistic | 53,022 | 0.477 | 0.334 | 0.866 | 0.557 |
| 5 | gbdt | 53,022 | 0.498 | 0.349 | 0.909 | 0.588 |

Diebold–Mariano on daily log loss: logistic beats both baselines at
h = 1 (−0.0062 against majority, p = 0.003; p = 0.003 against momentum)
but not at h = 5 (+0.0095, p = 0.10). LightGBM is worse than both
baselines at both horizons (p < 0.001): higher accuracy, overconfident
probabilities — calibration and regularisation are needed.

Backtest of the trading rules (logistic, h = 5, weekly rebalance),
2024-01-17 to 2026-11-17: **−37.0%** against **+57.5%** for VN30, with a
turnover of 51× a year and 23.8 million VND of fees and tax. As engine
checks, an oracle that knows the next five sessions returns several
hundred times the capital, and random forecasts lose 18.7% (costs, and
an equal-weight universe lagging a VN30 driven by a few large caps). The
5-session forecasts therefore carry no usable edge yet, and costs
dominate — the motivation for `feat/forecaster-v1` and
`feat/paper-trading-v1`.

## 13. Open questions

1. How is Arena's `BANKING` instrument defined, and is the 5D label
   `close(D+4) / close(D−1) − 1`? Check `/api/leaderboard/evaluation`.
2. Should indices get their own models instead of sharing the panel?

Answered on 2026-11-22:
- whether Arena's prices are adjusted: back-adjusted, but not completely
  (Section 5.3);
- the official VN30 list: verified (Section 5.2);
- a 2020 sample start: better but not significant; kept at 2023 and
  retested in forecaster-v1 (Section 5.4).

## 14. Timeline

Week-by-week plan and status: [`TODO.md`](../../TODO.md).

## 15. References

1. Chen, T., & Guestrin, C. (2016). XGBoost: A scalable tree boosting
   system. *Proceedings of KDD 2016*, 785–794.
2. Ke, G., Meng, Q., Finley, T., et al. (2017). LightGBM: A highly
   efficient gradient boosting decision tree. *NeurIPS 30*.
3. Krauss, C., Do, X. A., & Huck, N. (2017). Deep neural networks,
   gradient-boosted trees, random forests: Statistical arbitrage on the
   S&P 500. *European Journal of Operational Research*, 259(2), 689–702.
4. López de Prado, M. (2018). *Advances in Financial Machine Learning*.
   Wiley.
5. Lundberg, S. M., & Lee, S.-I. (2017). A unified approach to
   interpreting model predictions. *NeurIPS 30*.
6. Diebold, F. X., & Mariano, R. S. (1995). Comparing predictive
   accuracy. *Journal of Business & Economic Statistics*, 13(3), 253–263.
7. Arena – AI trading agents platform. [ckai.vn](https://ckai.vn),
   scoring rules and API documentation (accessed 2026-11-17).
