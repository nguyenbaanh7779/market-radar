# Architecture

How the system is built: components, the daily run, where data lives and
how the agent can be extended. The research decisions behind it are in
[`docs/strategy/README.md`](../strategy/README.md); every file and column
is described in [`data_dictionary.md`](data_dictionary.md); setup is in
[`docs/guide/README.md`](../guide/README.md).

## 1. Components

```
                 Arena API (default)  /  vnstock v6 (optional)
                                 │  data/sources.py
                                 ▼
   data/update.py ──> data/raw/bars/<SYMBOL>.parquet  (data/store.py, DuckDB)
                                 │  data/quality.py
                                 ▼
   dataset.py: assemble() — baskets, market state, sector rotation,
               features, labels  ──>  MarketData
           │                       │                         │
           ▼                       ▼                         ▼
   Module 1  signals/      Module 2  forecaster/     Module 3  trader/
   indicators, market,     labels, features,         broker (lots, T+2,
   sectors, tickers,  ───> models, walk_forward, ──> costs), strategy,
   portfolio  (features)   evaluate, agent  (P(UP))  backtest, metrics
           │                       │                         │
           └──────────────┬────────┴─────────────────────────┘
                          ▼
     report/ newsletter (Jinja2) ──> Telegram       forward.py ──> state/
```

| Package / module | Responsibility |
|---|---|
| `config.py`, `config/` | Typed settings, universe, holidays; `fingerprint()` versions the models |
| `calendar.py` | Realised sessions (VNINDEX dates) and projected future sessions |
| `data/` | Sources behind the `BarSource` protocol, Parquet store, incremental update, quality checks |
| `dataset.py` | One pass from stored bars to everything the modules need (`MarketData`) |
| `signals/` | Module 1: transparent rules, no training |
| `forecaster/` | Module 2: labels, point-in-time features, models behind `DirectionModel`, walk-forward and DM test, `ForecastAgent` |
| `trader/` | Module 3: `PaperBroker`, `target_weights` / `plan_orders` / `execute_orders`, `run_backtest` |
| `forward.py` | Append-only CSV logs, resolution of past forecasts, the paper account |
| `report/` | Newsletter template and Telegram delivery |
| `pipeline.py`, `cli.py` | Orchestration and the `market-radar` command |

Modules depend only downwards: `signals` and `forecaster` never import
`pipeline`, and `trader` knows nothing about how forecasts are made.

## 2. The daily run (`market-radar daily`)

1. Download new bars (`update_data`), then `assemble` everything.
2. Check that the expected session is published
   (`TradingCalendar.expected_asof`); if not, exit with code 3 so the
   workflow retries.
3. Fit every candidate model on all labels known now and forecast the
   last session for 1 and 5 sessions (`forecast_session`); append to
   `predictions.csv`.
4. Resolve earlier forecasts whose target session has closed
   (`resolve_predictions` → `resolved.csv`).
5. Compute the ticker flags (Module 1).
6. Advance the paper account (`paper_trading_step`): fill the pending
   orders at their session's close, log equity, plan the next orders
   (stop-losses every session, rebalance every 5).
7. Write the signal snapshot and the newsletter without the personal
   portfolio to `state/`; send the full newsletter to Telegram when new
   forecasts were added.

Every step is idempotent: running twice for the same session adds
nothing.

## 3. Where data lives

| Location | Content | In git? |
|---|---|---|
| `config/` | Settings, universe, holidays, portfolio template | Yes (`portfolio.yaml` is ignored) |
| `data/raw/bars/` | Downloaded bars | No — re-creatable; cached in CI |
| `data/results/` | Walk-forward and backtest results | No — re-creatable |
| `state/` | Forward-test logs, account, reports | No on `main`; yes on the orphan `data` branch |

## 4. Automation

| Workflow | Trigger | Does |
|---|---|---|
| `.github/workflows/ci.yml` | Push, pull request | `ruff check`, `pytest` on Python 3.12 |
| `.github/workflows/daily.yml` | 05:30 ICT Monday–Friday, manual | `market-radar daily`, commit `state/` to the `data` branch |

Secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `PORTFOLIO_YAML`.

## 5. Extension points

- **New data source:** implement `BarSource.fetch` in `data/sources.py`
  and register it in `make_source`.
- **New model:** subclass `DirectionModel` (`fit`, `predict_proba`,
  optional `explain`) and add it to `make_model` and
  `models.candidates`.
- **Specialised agents and a combiner:** each agent follows the
  `ForecastAgent` contract (data up to *t* → label, probabilities,
  explanation, version); a combiner consumes their outputs through the
  same contract.
- **New trading rule:** change `target_weights` / `plan_orders`; the
  broker enforces the market rules independently.
