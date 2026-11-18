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

## P1 — Research questions

- [ ] **`feat/data-understanding`** (W4) — notebook `01_data_understanding`
  - Coverage and quality per symbol; Arena vs vnstock closes if a key is
    available; exchange transfers (BSR, SHB, LPB, …) so price-limit checks
    use the limit of the period
  - Label balance by horizon and band θ ∈ {0.1, 0.2, 0.5}%; regime
    timeline 2019–2026
  - Verify the VN30 list against HOSE; decide 2020 vs 2023 as sample start
  - Done when: the decisions are recorded in docs/strategy Sections 5–6

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

- [ ] **`feat/vnstock-source`** — test the vnstock v6 adapter with a broker
  key; enable volume features and an evening run
- [ ] **`chore/universe-history`** — point-in-time VN30 membership to
  remove survivorship bias

## Report (W11–13)

- [ ] **`docs/report`** — LaTeX report in English (structure from
  docs/strategy), figures exported by the notebooks
- [ ] **`docs/slides`** — Beamer slides in English with the HUST theme
  (vendored as in customer-churn-prediction)
