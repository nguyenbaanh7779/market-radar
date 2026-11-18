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

78 symbols are requested: VNINDEX, VN30 and 76 stocks — the 30 VN30
constituents, 20 listed banks and 8 sectors (banking with all 20 banks;
real estate, securities, materials, consumer, technology, energy and
industrials with 5–11 representatives each). An equal-weight basket of the banks, **BANKS**, is built as an
instrument; it stands in for Arena's `BANKING` instrument, whose
definition is not published. All stocks are in Arena's universe except
MCH (added to VN30 in August 2026), for which Arena has no bars.

The VN30 list is reconstructed from the May and July 2026 HOSE reviews
and must be checked against the official list. Using today's
constituents over the whole history introduces **survivorship bias**: a
limitation to state in the report.

### 5.3 Quality rules

`market-radar check` reports, per symbol: sessions missing against the
VNINDEX calendar, duplicate dates, inconsistent OHLC, moves beyond the
exchange price limit (HOSE ±7%, HNX ±10%, UPCoM ±15%) and volume
coverage. A move beyond the limit usually marks a corporate action that
the series is not adjusted for (e.g. HPG −21% on 2021-05-31), so **labels
whose window spans such a move are voided**. Because exchange transfers
are not modelled yet (e.g. BSR and SHB, both listed on other exchanges
before HOSE), some legitimate older moves are voided too — conservative,
and refined in the data-understanding step.

## 6. Labels

For instrument *i* at session *t* and horizon *h*:

    r(i, t, h) = close(i, t + h) / close(i, t) − 1
    label = UP if r > +θ;  DOWN if r < −θ;  SIDEWAY otherwise

with h ∈ {1, 5} sessions and θ = 0.2%. With h = 1 this is exactly Arena's
`direction_brier_v1` rule (`return_pct = (close_D − close_{D−1}) /
close_{D−1}`, default band 0.2%). Arena's direction leaderboards are
`VN30` 1D, `BANKING` 1D and `VNINDEX` 5D, all with a 0.2% band.

SIDEWAY is the minority class at this band: 14.3% of 1-session and 4.9%
of 5-session labels in the 2024–2026 test period (DOWN 43.8% / 47.5%, UP
41.9% / 47.6%), so the 5-session problem is nearly binary. Many SIDEWAY
cases are unchanged closes of low-priced stocks, where one price tick
exceeds the band; the effect of θ is examined in the data-understanding
step.

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

GitHub Actions runs `market-radar daily` at 05:30 ICT on weekdays:
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
- **Unadjusted jumps** and exchange transfers in the price history
  (Section 5.3).
- **Data-source risk:** Arena's API is public but undocumented in parts
  and could change; vnstock needs a broker key; GitHub-hosted runners may
  be blocked by some Vietnamese sources.
- **Short forward test** (Section 10.3), and one market regime in it.
- **Not investment advice;** sharing the tool beyond the author needs a
  check of the rules on securities investment advice.

## 12. Baseline results of the skeleton (2026-11-17)

First run of `market-radar evaluate` and `backtest` on Arena data, with
the default settings of this document. These numbers are the starting
point that the planned work must beat, not results for the report.

Walk-forward 2024-01 to 2026-11 (34 folds per horizon, 78 instruments):

| h | Model | n | Accuracy | Balanced accuracy | Log loss | Brier |
|---|---|---|---|---|---|---|
| 1 | majority | 54,590 | 0.419 | 0.333 | 1.005 | 0.613 |
| 1 | momentum | 54,590 | 0.419 | 0.333 | 1.005 | 0.613 |
| 1 | logistic | 54,590 | 0.447 | 0.349 | **0.999** | **0.611** |
| 1 | gbdt | 54,590 | 0.441 | 0.346 | 1.023 | 0.629 |
| 5 | majority | 53,946 | 0.476 | 0.333 | **0.858** | **0.548** |
| 5 | momentum | 53,946 | 0.476 | 0.333 | 0.858 | 0.548 |
| 5 | logistic | 53,946 | 0.476 | 0.334 | 0.868 | 0.558 |
| 5 | gbdt | 53,946 | 0.496 | 0.348 | 0.911 | 0.589 |

Diebold–Mariano on daily log loss: logistic beats both baselines at
h = 1 (−0.0064 against majority, p = 0.002; p = 0.003 against momentum)
but not at h = 5 (+0.0097, p = 0.10). LightGBM is worse than both
baselines at both horizons (p < 0.001): higher accuracy, overconfident
probabilities — calibration and regularisation are needed.

Backtest of the trading rules (logistic, h = 5, weekly rebalance),
2024-01-17 to 2026-11-16: **−36.4%** against **+58.1%** for VN30, with a
turnover of 51× a year and 24.7 million VND of fees and tax. As engine
checks, an oracle that knows the next five sessions returns several
hundred times the capital, and random forecasts lose 18.7% (costs, and
an equal-weight universe lagging a VN30 driven by a few large caps). The
5-session forecasts therefore carry no usable edge yet, and costs
dominate — the motivation for `feat/forecaster-v1` and
`feat/paper-trading-v1`.

## 13. Open questions

1. How is Arena's `BANKING` instrument defined, and is the 5D label
   `close(D+4) / close(D−1) − 1`? Check `/api/leaderboard/evaluation`.
2. Are Arena's prices fully adjusted for corporate actions?
3. The official VN30 list (Section 5.2).
4. Should the training sample start in 2020 to include the 2022 bear
   market, rather than 2023 as proposed?
5. Should indices get their own models instead of sharing the panel?

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
