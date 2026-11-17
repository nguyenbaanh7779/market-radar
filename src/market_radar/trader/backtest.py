"""Replay out-of-sample forecasts as a paper-trading strategy."""

from __future__ import annotations

import dataclasses

import pandas as pd

from market_radar.calendar import TradingCalendar
from market_radar.config import TradingSettings
from market_radar.trader.broker import PaperBroker
from market_radar.trader.metrics import performance_metrics, trading_metrics
from market_radar.trader.strategy import (
    execute_orders,
    plan_orders,
    target_weights,
)


@dataclasses.dataclass
class BacktestResult:
    """Outcome of a backtest.

    Attributes:
        equity: Per session: strategy equity, cash, invested value,
            number of positions and the benchmark scaled to the same
            starting capital.
        trades: Every fill.
        unfilled: Orders that could not be filled.
    """

    equity: pd.DataFrame
    trades: pd.DataFrame
    unfilled: pd.DataFrame

    def summary(self) -> pd.DataFrame:
        """Compare the strategy with buy-and-hold of the benchmark.

        Returns:
            One row each for ``strategy`` and ``benchmark``.
        """
        strategy = performance_metrics(self.equity["equity_vnd"])
        strategy.update(trading_metrics(self.trades,
                                        self.equity["equity_vnd"]))
        benchmark = performance_metrics(self.equity["benchmark_vnd"])
        return pd.DataFrame({"strategy": strategy, "benchmark": benchmark}).T


def run_backtest(
    forecasts: pd.DataFrame,
    closes: pd.DataFrame,
    calendar: TradingCalendar,
    rules: TradingSettings,
) -> BacktestResult:
    """Trade the forecasts session by session.

    After each close the strategy plans orders from that session's
    forecasts; they are filled at the next session's close.

    Args:
        forecasts: Tradable stocks only: ``date``, ``symbol``, ``p_up``,
            ``p_down``.
        closes: Closes, dates by symbols (must include the benchmark).
        calendar: Trading calendar.
        rules: Trading rules.

    Returns:
        The equity curve, trades and unfilled orders.
    """
    first, last = forecasts["date"].min(), closes.index.max()
    sessions = calendar.sessions[(calendar.sessions >= first)
                                 & (calendar.sessions <= last)]
    valued = closes.ffill()
    by_date = dict(tuple(forecasts.groupby("date")))
    broker = PaperBroker(rules.initial_capital_vnd, rules)
    pending, trades, unfilled, rows = [], [], [], []
    for i, session in enumerate(sessions):
        prices = closes.loc[session]
        done, missed = execute_orders(broker, pending, prices, session,
                                      calendar)
        trades += done
        unfilled += missed
        marks = valued.loc[session]
        rows.append({
            "date": session,
            "equity_vnd": broker.equity_vnd(marks),
            "cash_vnd": broker.cash_vnd,
            "invested_vnd": broker.invested_vnd(marks),
            "positions": len(broker.symbols()),
        })
        pending = []
        if session in by_date and i + 1 < len(sessions):
            weights = target_weights(by_date[session], rules)
            pending = plan_orders(broker, weights, marks, session,
                                  sessions[i + 1], calendar)
    equity = pd.DataFrame(rows)
    benchmark = valued.loc[sessions, rules.benchmark].to_numpy()
    equity["benchmark_vnd"] = (rules.initial_capital_vnd * benchmark
                               / benchmark[0])
    return BacktestResult(
        equity=equity,
        trades=pd.DataFrame([dataclasses.asdict(t) for t in trades]),
        unfilled=pd.DataFrame([dataclasses.asdict(o) for o in unfilled]),
    )
