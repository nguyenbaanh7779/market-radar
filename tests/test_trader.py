import dataclasses

import numpy as np
import pandas as pd
import pytest

from market_radar.calendar import TradingCalendar
from market_radar.config import TradingSettings
from market_radar.trader.backtest import run_backtest
from market_radar.trader.broker import PaperBroker
from market_radar.trader.strategy import (
    Order,
    execute_orders,
    plan_orders,
    target_weights,
)

RULES = TradingSettings()
DAYS = pd.bdate_range("2026-11-02", periods=10)
CALENDAR = TradingCalendar(DAYS)


def test_buy_rounds_to_lots_and_charges_fee():
    broker = PaperBroker(10_000_000, RULES)
    trade = broker.buy("AAA", 250, 20.0, DAYS[0], "entry")
    assert trade.quantity == 200
    assert trade.value_vnd == 200 * 20.0 * 1000
    assert trade.fee_vnd == pytest.approx(4_000_000 * 0.0015)
    assert broker.cash_vnd == pytest.approx(10_000_000 - 4_006_000)


def test_buy_is_limited_by_cash():
    broker = PaperBroker(5_000_000, RULES)
    trade = broker.buy("AAA", 10_000, 20.0, DAYS[0], "entry")
    assert trade.quantity == 200          # 2 lots of 2,003,000 VND each
    assert broker.cash_vnd >= 0
    assert PaperBroker(1_000_000, RULES).buy(
        "AAA", 100, 20.0, DAYS[0], "entry") is None


def test_t_plus_2_settlement():
    broker = PaperBroker(10_000_000, RULES)
    broker.buy("AAA", 100, 20.0, DAYS[0], "entry")
    assert broker.sellable("AAA", DAYS[1], CALENDAR) == 0
    assert broker.sellable("AAA", DAYS[1], CALENDAR, ahead=1) == 100
    assert broker.sell("AAA", 100, 21.0, DAYS[1], CALENDAR, "exit") is None
    trade = broker.sell("AAA", 100, 21.0, DAYS[2], CALENDAR, "exit")
    assert trade.quantity == 100
    assert trade.fee_vnd == pytest.approx(2_100_000 * 0.0015)
    assert trade.tax_vnd == pytest.approx(2_100_000 * 0.001)
    assert broker.symbols() == []


def test_sell_takes_oldest_lots_first_and_snapshot_roundtrip():
    broker = PaperBroker(20_000_000, RULES)
    broker.buy("AAA", 100, 20.0, DAYS[0], "entry")
    broker.buy("AAA", 200, 22.0, DAYS[2], "add")
    assert broker.avg_price("AAA") == pytest.approx((2000 + 4400) / 300)
    broker.sell("AAA", 300, 23.0, DAYS[3], CALENDAR, "exit")
    assert broker.quantity("AAA") == 200       # only the first lot settled
    restored = PaperBroker.from_snapshot(broker.snapshot(), RULES)
    assert restored.quantity("AAA") == 200
    assert restored.cash_vnd == pytest.approx(broker.cash_vnd)


def test_target_weights_rules():
    forecasts = pd.DataFrame({
        "symbol": ["A", "B", "C", "D"],
        "p_up": [0.70, 0.55, 0.45, 0.35],
        "p_down": [0.20, 0.40, 0.50, 0.30],
    })
    rules = dataclasses.replace(RULES, top_k=2, max_weight=0.6)
    weights = target_weights(forecasts, rules)
    assert list(weights.index) == ["A", "B"]
    assert weights["A"] == pytest.approx(0.6)          # capped
    assert weights["B"] == pytest.approx(0.15 / 0.65)
    assert target_weights(forecasts.assign(p_up=0.1), rules).empty


def test_plan_orders_stop_loss_exit_and_entry():
    broker = PaperBroker(100_000_000, RULES)
    broker.buy("LOSER", 1000, 20.0, DAYS[0], "entry")
    broker.buy("OLD", 1000, 10.0, DAYS[0], "entry")
    broker.buy("FRESH", 1000, 10.0, DAYS[2], "entry")
    prices = pd.Series({"LOSER": 18.5, "OLD": 10.0, "FRESH": 10.0,
                        "NEW": 50.0})
    weights = pd.Series({"NEW": 0.2})
    orders = plan_orders(broker, weights, prices, DAYS[2], DAYS[3],
                         CALENDAR)
    by_symbol = {order.symbol: order for order in orders}
    assert by_symbol["LOSER"].reason == "stop_loss"     # -7.5%
    assert by_symbol["OLD"].reason == "exit"
    assert "FRESH" not in by_symbol                     # not settled yet
    assert by_symbol["NEW"].side == "buy"
    assert by_symbol["NEW"].quantity % 100 == 0
    assert by_symbol["NEW"].session == DAYS[3].date().isoformat()


def test_execute_orders_sells_before_buys_and_reports_unfilled():
    broker = PaperBroker(2_100_000, RULES)
    broker.buy("AAA", 100, 20.0, DAYS[0], "entry")
    orders = [Order("x", "BBB", "buy", 100, "entry"),
              Order("x", "AAA", "sell", 100, "exit"),
              Order("x", "CCC", "buy", 100, "entry")]
    prices = pd.Series({"AAA": 20.0, "BBB": 20.0})
    trades, unfilled = execute_orders(broker, orders, prices, DAYS[2],
                                      CALENDAR)
    assert [t.symbol for t in trades] == ["AAA", "BBB"]
    assert [o.symbol for o in unfilled] == ["CCC"]       # no price


def test_backtest_fills_at_next_close_and_respects_rules():
    days = pd.bdate_range("2026-01-05", periods=60)
    calendar = TradingCalendar(days)
    rising = 20.0 * np.cumprod(np.full(60, 1.004))
    closes = pd.DataFrame({"UPP": rising, "VN30": np.linspace(1000, 1050,
                                                              60)},
                          index=days)
    forecasts = pd.DataFrame({"date": days, "symbol": "UPP",
                              "p_up": 0.8, "p_down": 0.1})
    result = run_backtest(forecasts, closes, calendar, RULES)
    first = result.trades.iloc[0]
    assert first["session"] == days[1].date().isoformat()
    assert first["price"] == pytest.approx(rising[1])
    assert (result.trades["quantity"] % 100 == 0).all()
    assert (result.equity["cash_vnd"] >= 0).all()
    assert result.equity["equity_vnd"].iloc[-1] > RULES.initial_capital_vnd
    summary = result.summary()
    assert summary.loc["strategy", "fees_vnd"] > 0
    assert summary.loc["benchmark", "total_return_pct"] == pytest.approx(5.0)


def test_between_rebalances_only_stop_losses_are_planned():
    broker = PaperBroker(100_000_000, RULES)
    broker.buy("LOSER", 1000, 20.0, DAYS[0], "entry")
    broker.buy("OLD", 1000, 10.0, DAYS[0], "entry")
    prices = pd.Series({"LOSER": 18.5, "OLD": 10.0, "NEW": 50.0})
    orders = plan_orders(broker, pd.Series({"NEW": 0.2}), prices, DAYS[2],
                         DAYS[3], CALENDAR, rebalance=False)
    assert [(o.symbol, o.reason) for o in orders] == [("LOSER", "stop_loss")]


def test_rebalance_due():
    from market_radar.trader.strategy import rebalance_due
    assert rebalance_due(CALENDAR, DAYS[0], None, 5)
    assert not rebalance_due(CALENDAR, DAYS[4], DAYS[0], 5)
    assert rebalance_due(CALENDAR, DAYS[5], DAYS[0], 5)
