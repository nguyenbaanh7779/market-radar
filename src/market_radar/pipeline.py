"""Orchestration of the CLI commands: update, evaluate, backtest, daily."""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from market_radar.calendar import to_day
from market_radar.config import Settings
from market_radar.data.sources import make_source
from market_radar.data.store import BarStore
from market_radar.data.update import update_bars
from market_radar.dataset import MarketData, assemble
from market_radar.forecaster.agent import ForecastAgent
from market_radar.forecaster.evaluate import (
    metrics_table,
    score_rows,
    significance_table,
    walk_forward_predictions,
)
from market_radar.forecaster.walk_forward import walk_forward_folds
from market_radar.forward import (
    PREDICTION_KEY,
    ForwardState,
    orders_to_records,
    resolve_predictions,
)
from market_radar.report import newsletter
from market_radar.report.telegram import send_telegram
from market_radar.signals.portfolio import load_holdings, portfolio_status
from market_radar.signals.tickers import ticker_flags
from market_radar.trader.backtest import BacktestResult, run_backtest
from market_radar.trader.strategy import (
    Order,
    execute_orders,
    plan_orders,
    rebalance_due,
    target_weights,
)

logger = logging.getLogger(__name__)
BASELINES = ("majority", "momentum")
PORTFOLIO_ENV_VAR = "MARKET_RADAR_PORTFOLIO"


class DataNotReady(RuntimeError):
    """The bars a run needs have not been published yet."""


def bar_store(settings: Settings) -> BarStore:
    """Return the store of raw bars.

    Args:
        settings: Run settings.

    Returns:
        Store under ``<data_dir>/raw/bars``.
    """
    return BarStore(settings.data_dir / "raw" / "bars")


def results_dir(settings: Settings) -> Path:
    """Return (and create) the folder for evaluation results.

    Args:
        settings: Run settings.

    Returns:
        ``<data_dir>/results``.
    """
    path = settings.data_dir / "results"
    path.mkdir(parents=True, exist_ok=True)
    return path


def local_today(settings: Settings) -> dt.date:
    """Return today's date in the market's time zone.

    Args:
        settings: Run settings.

    Returns:
        The local date.
    """
    return dt.datetime.now(ZoneInfo(settings.schedule.timezone)).date()


def update_data(
    settings: Settings,
    symbols: list[str] | None = None,
    start: dt.date | None = None,
    source_name: str | None = None,
) -> pd.DataFrame:
    """Download new bars for the universe.

    Args:
        settings: Run settings.
        symbols: Symbols to update (default: the whole universe).
        start: First date for symbols without bars (default: fetch_start).
        source_name: Source overriding the configured one.

    Returns:
        The per-symbol update report.
    """
    return update_bars(
        bar_store(settings),
        make_source(settings, source_name),
        symbols or list(settings.universe.fetch_symbols),
        start or settings.data.fetch_start,
        local_today(settings),
        settings.data.overlap_days,
    )


def load_market_data(settings: Settings) -> MarketData:
    """Load stored bars and assemble signals, features and labels.

    Args:
        settings: Run settings.

    Returns:
        The assembled market data.
    """
    raw = bar_store(settings).load(settings.universe.fetch_symbols)
    return assemble(raw, settings)


def evaluate(
    settings: Settings,
    data: MarketData,
    horizons: tuple[int, ...] | None = None,
    models: tuple[str, ...] | None = None,
) -> dict[str, pd.DataFrame]:
    """Run walk-forward validation and save the results.

    Args:
        settings: Run settings.
        data: Assembled market data.
        horizons: Horizons to evaluate (default: all configured).
        models: Models to evaluate (default: all candidates).

    Returns:
        Tables ``metrics``, ``folds``, ``significance`` and ``oos``.
    """
    horizons = horizons or settings.labels.horizons
    models = models or settings.models.candidates
    start = pd.Timestamp(settings.data.sample_start)
    sessions = data.calendar.sessions[data.calendar.sessions >= start]
    wf = settings.walk_forward
    parts = []
    for horizon in horizons:
        folds = walk_forward_folds(sessions, wf.min_train_sessions,
                                   wf.test_sessions, horizon,
                                   wf.embargo_sessions)
        panel = data.panel[data.panel["date"] >= start]
        parts.append(walk_forward_predictions(
            panel, data.feature_cols, horizon, models, folds, settings))
    scored = score_rows(pd.concat(parts, ignore_index=True))
    candidates = [m for m in models if m not in BASELINES]
    baselines = [m for m in models if m in BASELINES]
    tables = {
        "metrics": metrics_table(scored, ["horizon", "model"]),
        "folds": metrics_table(scored, ["horizon", "model", "fold"]),
        "significance": significance_table(scored, candidates, baselines),
        "oos": scored,
    }
    out = results_dir(settings)
    for name in ("metrics", "folds", "significance"):
        tables[name].to_csv(out / f"wf_{name}.csv", index=False)
    scored.to_parquet(out / "oos_predictions.parquet", index=False)
    return tables


def backtest(
    settings: Settings, data: MarketData, oos: pd.DataFrame | None = None
) -> BacktestResult:
    """Backtest the trading rules on out-of-sample forecasts.

    Args:
        settings: Run settings.
        data: Assembled market data.
        oos: Scored walk-forward predictions (read from the results
            folder when omitted).

    Returns:
        The backtest result (also saved to the results folder).

    Raises:
        FileNotFoundError: If no walk-forward predictions exist yet.
    """
    if oos is None:
        path = results_dir(settings) / "oos_predictions.parquet"
        if not path.is_file():
            raise FileNotFoundError("Run `market-radar evaluate` first")
        oos = pd.read_parquet(path)
    rules = settings.trading
    chosen = oos[(oos["model"] == settings.models.primary)
                 & (oos["horizon"] == rules.horizon)
                 & oos["symbol"].isin(settings.universe.stocks)]
    result = run_backtest(chosen[["date", "symbol", "p_up", "p_down"]],
                          data.closes, data.calendar, rules)
    out = results_dir(settings)
    result.equity.to_csv(out / "backtest_equity.csv", index=False)
    result.trades.to_csv(out / "backtest_trades.csv", index=False)
    result.summary().to_csv(out / "backtest_summary.csv")
    return result


@dataclasses.dataclass
class DailyOutcome:
    """What a daily run produced.

    Attributes:
        asof: Session the run is based on.
        next_session: Session the forecasts and orders are for.
        new_predictions: Predictions added to the log.
        resolved: Predictions scored in this run.
        report_path: Saved newsletter (without the portfolio).
        report: Full newsletter text.
        sent: Telegram messages sent.
    """

    asof: pd.Timestamp
    next_session: pd.Timestamp
    new_predictions: int
    resolved: int
    report_path: Path
    report: str
    sent: int = 0


def daily(
    settings: Settings,
    state_dir: Path,
    today: dt.date | None = None,
    update: bool = True,
    send: bool = False,
) -> DailyOutcome:
    """Run the whole agent once: data, signals, forecasts, trading, report.

    Safe to repeat: logs skip rows they already hold and the paper
    account only processes sessions it has not seen.

    Args:
        settings: Run settings.
        state_dir: Forward-test state folder.
        today: Local run date (default: today in the market time zone).
        update: Whether to download new bars first.
        send: Whether to send the newsletter to Telegram (only when the
            run added new predictions).

    Returns:
        Summary of the run.

    Raises:
        DataNotReady: If the bars of the expected session are missing.
    """
    today = today or local_today(settings)
    if update:
        update_data(settings)
    data = load_market_data(settings)
    expected = data.calendar.expected_asof(
        today, settings.schedule.publish_lag_days)
    if data.asof < expected:
        raise DataNotReady(
            f"Latest bars are for {data.asof.date()}, expected "
            f"{expected.date()}; the source has not published yet.")
    asof = data.asof
    next_session = data.calendar.session_after(asof)
    state = ForwardState(state_dir)
    rows = data.panel[data.panel["date"] == asof]
    forecasts = forecast_session(settings, data, rows)
    new = state.append("predictions", forecasts, PREDICTION_KEY)
    resolved = resolve_predictions(
        state.read("predictions"), state.read("resolved"), data.closes,
        data.calendar, settings.labels.sideway_band_pct)
    state.append("resolved", resolved, PREDICTION_KEY)
    flags = ticker_flags(
        rows[rows["symbol"].isin(settings.universe.stocks)]
        .set_index("symbol"), settings.signals)
    paper = paper_trading_step(settings, data, state, forecasts,
                               next_session)
    context = report_context(settings, data, forecasts, flags, paper,
                             next_session)
    state.write_text("signals", asof, ".json",
                     signals_snapshot(data, flags, asof))
    language = settings.report.language
    path = state.write_text(
        "reports", asof, ".md",
        newsletter.render(context, include_portfolio=False,
                          language=language))
    report = newsletter.render(context, language=language)
    outcome = DailyOutcome(asof, next_session, new, len(resolved), path,
                           report)
    if send and new:
        outcome.sent = deliver(report)
    logger.info("Daily run for %s: %d new predictions, %d resolved, "
                "%d messages sent", asof.date(), new, len(resolved),
                outcome.sent)
    return outcome


def forecast_session(
    settings: Settings, data: MarketData, rows: pd.DataFrame
) -> pd.DataFrame:
    """Fit every candidate model on all labels known now and predict.

    Args:
        settings: Run settings.
        data: Assembled market data.
        rows: Feature rows of the session to forecast from.

    Returns:
        Prediction log rows for every model and horizon.
    """
    created = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    sha = git_sha(settings.root)
    parts = []
    for horizon in settings.labels.horizons:
        target = data.calendar.session_after(data.asof, horizon)
        for name in settings.models.candidates:
            agent = ForecastAgent(name, horizon, data.feature_cols, settings)
            out = agent.fit(data.panel).predict(rows)
            out["asof_date"] = data.asof.date().isoformat()
            out["target_date"] = target.date().isoformat()
            out["asof_close"] = rows["close"].to_numpy()
            out["created_at_utc"] = created
            out["git_sha"] = sha
            parts.append(out)
    columns = ["created_at_utc", "asof_date", "target_date", "symbol",
               "horizon", "model", "model_version", "git_sha", "p_down",
               "p_sideway", "p_up", "label_pred", "asof_close",
               "explanation"]
    return pd.concat(parts, ignore_index=True)[columns]


def paper_trading_step(
    settings: Settings,
    data: MarketData,
    state: ForwardState,
    forecasts: pd.DataFrame,
    next_session: pd.Timestamp,
) -> dict[str, Any]:
    """Advance the forward paper account to the latest session.

    Fills the orders of every session not processed yet at that
    session's close, logs equity, then plans orders for the next session
    from today's forecasts.

    Args:
        settings: Run settings.
        data: Assembled market data.
        state: Forward-test state.
        forecasts: Today's prediction rows.
        next_session: Session the new orders are for.

    Returns:
        Values for the newsletter's paper-trading section.
    """
    rules = settings.trading
    broker, meta = state.load_account(rules)
    asof, calendar = data.asof, data.calendar
    marks = data.closes.ffill()
    last = meta["last_session"]
    if last is None or to_day(last) < asof:
        sessions = calendar.sessions[calendar.sessions <= asof]
        if last is not None:
            sessions = sessions[sessions > to_day(last)]
        else:
            sessions = sessions[-1:]
            meta["started"] = asof.date().isoformat()
        pending = [Order(**order) for order in meta["pending"]]
        for session in sessions:
            due = [o for o in pending
                   if to_day(o.session) <= session]
            pending = [o for o in pending if to_day(o.session) > session]
            trades, _ = execute_orders(
                broker, [o for o in due if to_day(o.session) == session],
                data.closes.loc[session], session, calendar)
            state.append("trades", pd.DataFrame(
                [dataclasses.asdict(t) for t in trades]))
            state.append("equity", pd.DataFrame([{
                "date": session.date().isoformat(),
                "equity_vnd": broker.equity_vnd(marks.loc[session]),
                "cash_vnd": broker.cash_vnd,
                "positions": len(broker.symbols()),
                "benchmark_close": marks.at[session, rules.benchmark],
            }]), key=["date"])
        chosen = forecasts[
            (forecasts["model"] == settings.models.primary)
            & (forecasts["horizon"] == rules.horizon)
            & forecasts["symbol"].isin(settings.universe.stocks)]
        last_rebalance = meta.get("last_rebalance")
        rebalance = rebalance_due(
            calendar, asof, to_day(last_rebalance) if last_rebalance
            else None, rules.rebalance_every_sessions)
        weights = target_weights(chosen, rules)
        orders = plan_orders(broker, weights, marks.loc[asof], asof,
                             next_session, calendar, rebalance)
        state.append("orders", orders_to_records(orders, asof))
        meta["pending"] = [dataclasses.asdict(o) for o in orders]
        meta["last_session"] = asof.date().isoformat()
        if rebalance:
            meta["last_rebalance"] = asof.date().isoformat()
        state.save_account(broker, meta)
    return paper_summary(settings, data, state, broker, meta)


def paper_summary(
    settings: Settings,
    data: MarketData,
    state: ForwardState,
    broker: Any,
    meta: dict[str, Any],
) -> dict[str, Any]:
    """Summarise the paper account for the newsletter.

    Args:
        settings: Run settings.
        data: Assembled market data.
        state: Forward-test state.
        broker: Paper account.
        meta: Account metadata.

    Returns:
        Equity, returns against the benchmark, holdings and orders.
    """
    rules = settings.trading
    started = meta.get("started")
    if not started:
        return {"started": None}
    marks = data.closes.ffill().loc[data.asof]
    benchmark = data.closes[rules.benchmark].dropna()
    base = benchmark.loc[to_day(started):].iloc[0]
    equity = broker.equity_vnd(marks)
    holdings = [{"symbol": s, "quantity": broker.quantity(s)}
                for s in broker.symbols()]
    return {
        "started": started,
        "equity_vnd": equity,
        "return_pct": 100.0 * (equity / rules.initial_capital_vnd - 1.0),
        "benchmark": rules.benchmark,
        "benchmark_return_pct": 100.0 * (benchmark.loc[data.asof] / base
                                         - 1.0),
        "holdings": holdings,
        "orders": list(meta["pending"]),
    }


def report_context(
    settings: Settings,
    data: MarketData,
    forecasts: pd.DataFrame,
    flags: pd.DataFrame,
    paper: dict[str, Any],
    next_session: pd.Timestamp,
) -> dict[str, Any]:
    """Collect everything the newsletter template needs.

    Args:
        settings: Run settings.
        data: Assembled market data.
        forecasts: Today's prediction rows.
        flags: Technical flags by symbol.
        paper: Paper-trading summary.
        next_session: Session the outlook is for.

    Returns:
        Template context.
    """
    asof = data.asof
    stocks = list(settings.universe.stocks)
    primary = settings.models.primary
    strong, caution = newsletter.ranked_stocks(
        forecasts, flags, stocks, primary, settings.trading.horizon,
        settings.report.top_n)
    top, bottom = newsletter.sector_rows(data.rotation, asof)
    quadrants = (data.rotation[data.rotation["date"] == asof]
                 .set_index("sector")["quadrant"].to_dict())
    holdings, since = load_holdings(portfolio_path(settings))
    portfolio = portfolio_status(
        holdings, data.closes, asof, settings.universe.sector_of,
        quadrants, flags, settings.trading.benchmark, since,
        settings.trading.price_unit_vnd)
    return {
        "asof": asof.date().isoformat(),
        "next_session": next_session.date().isoformat(),
        "market": newsletter.market_summary(data.market, data.closes, asof),
        "outlook": newsletter.outlook_rows(
            forecasts, list(settings.report.outlook_symbols), primary),
        "sectors_top": top,
        "sectors_bottom": bottom,
        "strong": strong,
        "caution": caution,
        "portfolio": portfolio,
        "paper": paper,
        "models": f"{primary} (v{settings.fingerprint()})",
        "data_source": settings.data.source,
        "has_volume": data.has_volume,
    }


def signals_snapshot(
    data: MarketData, flags: pd.DataFrame, asof: pd.Timestamp
) -> str:
    """Serialise the Module 1 signals of a session.

    Args:
        data: Assembled market data.
        flags: Technical flags by symbol.
        asof: Session to serialise.

    Returns:
        JSON text with the market state, sector rotation and flags.
    """
    market = data.market.loc[[asof]]
    rotation = data.rotation[data.rotation["date"] == asof]
    payload = {
        "asof": asof.date().isoformat(),
        "market": _records(market)[0],
        "sectors": _records(rotation.drop(columns="date")),
        "flags": _records(flags.reset_index(names="symbol")),
    }
    return json.dumps(payload, indent=2)


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a frame to JSON-safe records (NaN becomes null).

    Args:
        frame: Any frame.

    Returns:
        One dict per row.
    """
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def portfolio_path(settings: Settings) -> Path:
    """Locate the user's holdings file.

    Args:
        settings: Run settings.

    Returns:
        ``$MARKET_RADAR_PORTFOLIO`` or ``config/portfolio.yaml``.
    """
    custom = os.environ.get(PORTFOLIO_ENV_VAR)
    return Path(custom) if custom else settings.config_dir / "portfolio.yaml"


def deliver(report: str) -> int:
    """Send the newsletter to Telegram when credentials are configured.

    Args:
        report: Newsletter text.

    Returns:
        Messages sent (0 without ``TELEGRAM_BOT_TOKEN``/``_CHAT_ID``).
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        logger.info("Telegram is not configured; newsletter not sent")
        return 0
    return send_telegram(report, token, chat_id)


def git_sha(root: Path) -> str:
    """Return the commit the code runs from.

    Args:
        root: Repository root.

    Returns:
        ``$GITHUB_SHA``, else ``git rev-parse --short HEAD``, else
        ``unknown``.
    """
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"][:12]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"], cwd=root,
            capture_output=True, text=True, check=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return result.stdout.strip() or "unknown"
