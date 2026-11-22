# TODO

Work plan for DX6000 (2026-11-02 to 2027-01-31, 13 weeks), following the
[research design](docs/strategy/README.md). Each item is one branch from
the latest `main`; after a squash-merge, start the next one from the new
`main`.

Priority: **P1** needed for the research questions · **P2** core of the
product · **P3** polish and extensions. Items are in dependency order;
the week is the target, not a deadline.

## Done

- [x] **`feat/walking-skeleton`** (W3) — runnable end-to-end agent: data
  layer (Arena, optional vnstock v6), Module 1 signals, Module 2
  forecaster with walk-forward evaluation and DM test, Module 3 paper
  trading and backtest, daily pipeline with newsletter and Telegram, CI
  and the daily GitHub Actions job, research design and docs
- [x] **`feat/data-understanding`** (W4) — notebook
  `01_data_understanding`. Changes:
  - price limits follow the exchange of the day (13 transfers, checked
    against the press);
  - copied bars void labels;
  - Arena's adjustment is partial;
  - PNJ's July 2026 fall is genuine;
  - θ stays at 0.2%;
  - the sample stays from 2023 (2020 better but p ≈ 0.1);
  - VN30 verified (BVH → VPL).

  Arena vs vnstock is not compared (no broker key).

## Now (W4, 23–29/11)

- [ ] **Start the forward test on the Mac** — merge `feat/mac-runner`, run
  `scripts/macos/install.sh`, then one run with `launchctl kickstart`
  (docs/guide Section 3)
  - Done when: the `data` branch has its first commit and the newsletter
    arrives on Telegram
- [ ] **Ask Arena about cloud access** (you) — register an agent on ckai.vn
  and ask whether `/eod/market-bars` can be used from GitHub Actions (API
  key or allow-list); GitHub's runners currently get HTTP 403
  - Done when: the `daily` workflow is enabled again, or the Mac stays the
    runner with Arena's answer recorded in docs/strategy

- [ ] **Get an SSI FastConnect Data key** (you) — vnstock 4.x/5.x and the
  personal `vnstock_…` key stopped working on 2026-11-10 (Decree
  363/2026); vnstock 6 needs a broker key. Register FastConnect **Data**
  (not Trading) through your SSI broker or a branch, confirm by email,
  then create the connection on iBoard → Dịch vụ API and save ConsumerID
  and ConsumerSecret (shown once). Install vnstock 6 in `.venv` and run
  `vnstock keys set ssi`, `vnstock keys check ssi`, `vnstock doctor`
  (docs/guide Section 4)
  - Done when: `vnstock keys check ssi` passes; then start
    `feat/vnstock-source`

## P1 — Research questions

- [ ] **`chore/hnx-transfer`** (W9, after 2026-12-28) — all HNX stocks
  move to HOSE on 2026-12-28 (last HNX session 2026-12-23)
  - Once HOSE publishes the price limit for them, move SHS, MBS, PVS and
    IDC to HOSE in `config/universe.yaml` and add
    `{exchange: HNX, until: "2026-12-23"}` to `exchange_history`
  - Done when: `market-radar check` flags no legitimate move of these
    stocks after the transfer

- [ ] **`feat/holdout-split`** (W5, before `feat/forecaster-v1`) — keep a
  final test period untouched by model selection
  - Today every walk-forward test block (01/2024–11/2026) is used for
    evaluation and there is no validation set (hyperparameters are fixed
    in `config/settings.yaml`). Choosing models on these blocks would bias
    the reported results upwards (selection bias)
  - Split: walk-forward dev 01/2024 → ~05/2026 (model comparison and
    tuning), holdout ~06/2026 → 11/2026 (run once with the chosen model),
    forward test 11/2026 → 01/2027 (truly unseen, RQ5)
  - Add `walk_forward.holdout_start` to `config/settings.yaml`; `evaluate`
    runs only the folds before it, `evaluate --holdout` the rest
  - Tuning uses an inner validation block inside each fold's training
    window, never the fold's test block
  - Done when: docs/strategy Section 8.3 describes the three periods and
    the holdout has not been looked at before the model is chosen

- [ ] **`feat/forecaster-v1`** (W5–6) — notebook `03_modeling` (RQ2)
  - XGBoost; LSTM as a comparison only
  - Hyperparameter tuning inside the walk-forward (inner validation block,
    see `feat/holdout-split`); class-imbalance
    handling (class weights or a threshold on P(SIDEWAY))
  - Probability calibration (isotonic / Platt on an inner block); keep
    only if Brier improves without hurting log loss
  - Separate index models (VNINDEX, VN30, BANKS) vs the shared panel
  - Training from 2020 instead of 2023: lower log loss on the dev folds
    but not significant (p = 0.09 at h = 1, 0.11 at h = 5; docs/strategy
    Section 5.4). Retest with the chosen model; richer models may gain
    more from the 2020–2022 crash, boom and bust
  - Binary variant for the trading horizon: UP (`r > θ`) vs not UP, all
    rows kept (dropping SIDEWAY rows would train on a different
    distribution). Compare with the 3-class model on the log loss of
    P(UP) and in the backtest. Keep 3 classes as the label definition and
    for the 1-session index forecasts: SIDEWAY is 20–21% of 1-session
    labels for VNINDEX/VN30/BANKS (14% for stocks, 4.8% for stocks at
    5 sessions), and Arena scores 3 classes. If the binary variant is
    adopted for trading, add it to "Changes from the proposal" in
    docs/strategy
  - Done when: one model is chosen with a DM p-value against both
    baselines for h = 1 and h = 5

- [ ] **`feat/explain-ablation`** (W6) — notebook `04_explainability` (RQ3)
  - SHAP summary of the chosen model; ablation by feature group (drop one
    group at a time, walk-forward log loss and DM test)
  - Done when: a table ranks the signal groups by contribution

- [ ] **`docs/backtest-engines`** (W6, supervisor's request 2026-11-17) —
  survey existing backtest engines before extending Module 3 (RQ4)
  - Candidates: backtrader, vectorbt, backtesting.py, zipline-reloaded,
    bt, NautilusTrader, QuantConnect LEAN; check maintenance status and
    licence
  - Compare on what this project needs: event-driven vs vectorised, daily
    bars, board lots, T+2 settlement, ±7/10/15% price limits, fee and
    selling-tax models, fills at the next close, multi-asset portfolios,
    metrics and reports, speed on ~75 stocks × 2,000 sessions
  - Cross-check: replay the current strategy in one or two engines and
    compare equity curves with `trader/backtest.py` (should match within
    rounding when the rules are aligned)
  - Decide: keep the custom engine, adopt one, or keep both (one as a
    reference check); record it in docs/strategy Section 9
  - Done when: a comparison table and the decision are in docs/strategy,
    with the cross-check result

- [ ] **`feat/paper-trading-v1`** (W7) — notebook `05_backtest` (RQ4)
  - Build on the engine chosen in `docs/backtest-engines`
  - Sensitivity to fees, top-k, stop-loss, weights and the 1D vs 5D
    signal; benchmark also against the E1VFVN30 ETF
  - Done when: strategy vs VN30 table with costs, plus the sensitivity
    grid in an appendix

- [ ] **`feat/forward-analysis`** (W10–11) — notebook `06_forward_test`
  (RQ5)
  - Forward metrics vs walk-forward fold distribution; paper account vs a
    backtest of the same sessions
  - Done when: RQ5 is answered with the number of sessions stated

## P2 — Product

- [ ] **`feat/signals-v1`** (W5) — notebook `02_signals`
  - Sanity checks of regime, breadth and rotation against known episodes
  - Tune flag thresholds; add sector flow to the portfolio warnings
  - Done when: the newsletter sections read well on 10 sample days

- [ ] **`feat/dashboard`** (W8) — Streamlit: overview → sector → stock →
  portfolio, reading the `data` branch state
  - Done when: it runs from the state files without retraining

- [ ] **`feat/delivery-feedback`** (W8–9) — email delivery; daily RQ1 log
  (reading time, usefulness 1–5, insight acted on), e.g. Telegram buttons
  - Done when: at least 20 logged days by W12

## P3 — Extensions and polish

- [ ] **`feat/arena`** (W6–7, optional) — submit VN30 1D, BANKING 1D and
  VNINDEX 5D predictions (and paper orders) to Arena before 08:05 ICT
  - Start by about 2026-12-15 to reach 30 resolved predictions by the end
  - Done when: the agent appears on the Arena leaderboards

- [ ] **`feat/vnstock-source`** (after the SSI key) — second data source
  through vnstock 6 with `source="ssi"`
  - Run the `VnstockSource` adapter on a few stocks and the indices; fix
    what differs from the live API
  - Check what SSI gives: history start, adjusted or raw prices
    (`ClosePriceAdjusted`), rate limits; volume and value are in DailyOhlc
  - Notebook comparing SSI with Arena: closes, the 2021 stock dividends,
    TCX and FPT in 2026-09, PNJ in 2026-07
  - Decide: keep Arena prices and add SSI volume (re-enable liquidity
    features), or switch; evening run only if SSI has the bars the same day
  - Set the key up on the runner clone only once SSI is adopted
  - Done when: the comparison and the decision are recorded in
    docs/strategy Section 5
- [ ] **`chore/universe-history`** — point-in-time VN30 membership to
  remove survivorship bias

## Report (W11–13)

- [ ] **`docs/report`** — LaTeX report in English (structure from
  docs/strategy), figures exported by the notebooks
- [ ] **`docs/slides`** — Beamer slides in English with the HUST theme
  (vendored as in customer-churn-prediction)
