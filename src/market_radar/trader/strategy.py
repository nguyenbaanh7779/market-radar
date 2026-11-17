"""Turn forecasts into orders: top-k by P(UP), confidence weights, stops.

Decisions are taken after the close of session ``t`` and filled at the
close of the next session (an ATC order), so no decision uses a price it
could not have seen.
"""

from __future__ import annotations

import dataclasses
import math

import pandas as pd

from market_radar.calendar import TradingCalendar
from market_radar.config import TradingSettings
from market_radar.trader.broker import PaperBroker, Trade


@dataclasses.dataclass(frozen=True)
class Order:
    """An order to fill at the close of ``session``.

    Attributes:
        session: Fill session as ``YYYY-MM-DD``.
        symbol: Stock symbol.
        side: ``buy`` or ``sell``.
        quantity: Shares (whole lots).
        reason: ``entry``, ``add``, ``exit`` or ``stop_loss``.
    """

    session: str
    symbol: str
    side: str
    quantity: int
    reason: str


def target_weights(
    forecasts: pd.DataFrame, rules: TradingSettings
) -> pd.Series:
    """Choose the stocks to hold and their portfolio weights.

    Candidates need ``P(UP) >= min_p_up`` and ``P(UP) > P(DOWN)``; the
    ``top_k`` highest P(UP) are kept and weighted by ``P(UP) - P(DOWN)``,
    each capped at ``max_weight`` (the rest stays in cash).

    Args:
        forecasts: One row per stock with ``symbol``, ``p_up``, ``p_down``.
        rules: Trading rules.

    Returns:
        Weights by symbol (empty when nothing qualifies).
    """
    eligible = forecasts[(forecasts["p_up"] >= rules.min_p_up)
                         & (forecasts["p_up"] > forecasts["p_down"])]
    top = eligible.nlargest(rules.top_k, "p_up")
    edge = (top["p_up"] - top["p_down"]).to_numpy()
    if top.empty or edge.sum() <= 0:
        return pd.Series(dtype=float)
    weights = pd.Series(edge / edge.sum(), index=top["symbol"].to_numpy())
    return weights.clip(upper=rules.max_weight)


def rebalance_due(
    calendar: TradingCalendar,
    session: pd.Timestamp,
    last_rebalance: pd.Timestamp | None,
    every: int,
) -> bool:
    """Tell whether the portfolio is rebalanced after this session.

    Args:
        calendar: Trading calendar.
        session: Session just closed.
        last_rebalance: Session of the previous rebalance, if any.
        every: Sessions between rebalances.

    Returns:
        True on the first session and every ``every`` sessions after.
    """
    if last_rebalance is None:
        return True
    elapsed = calendar.position(session) - calendar.position(last_rebalance)
    return elapsed >= every


def plan_orders(
    broker: PaperBroker,
    weights: pd.Series,
    prices: pd.Series,
    session: pd.Timestamp,
    next_session: pd.Timestamp,
    calendar: TradingCalendar,
    rebalance: bool = True,
) -> list[Order]:
    """Plan the orders for the next session after the close of ``session``.

    Holdings at or below the stop-loss are sold every session as soon as
    they have settled. On rebalance sessions, holdings no longer targeted
    are sold too and targets below their weight are bought in whole lots.
    Stopped-out stocks are not bought back the same day.

    Args:
        broker: Current account.
        weights: Target weights by symbol.
        prices: Closes of ``session`` by symbol.
        session: Session just closed.
        next_session: Session the orders are for.
        calendar: Trading calendar.
        rebalance: Whether this is a rebalance session.

    Returns:
        Orders, sells first.
    """
    rules = broker.rules
    day = next_session.date().isoformat()
    equity = broker.equity_vnd(prices)
    orders, stopped = [], set()
    for symbol in broker.symbols():
        settled = broker.sellable(symbol, session, calendar, ahead=1)
        if settled == 0:
            continue
        stop_price = broker.avg_price(symbol) * (
            1.0 - rules.stop_loss_pct / 100.0)
        if prices[symbol] <= stop_price:
            orders.append(Order(day, symbol, "sell", settled, "stop_loss"))
            stopped.add(symbol)
        elif rebalance and symbol not in weights.index:
            orders.append(Order(day, symbol, "sell", settled, "exit"))
    if not rebalance:
        return orders
    for symbol, weight in weights.items():
        price = prices.get(symbol, math.nan)
        if symbol in stopped or not price > 0:
            continue
        held = broker.quantity(symbol)
        gap_vnd = weight * equity - held * price * rules.price_unit_vnd
        lot_vnd = rules.lot_size * price * rules.price_unit_vnd
        shares = int(gap_vnd // lot_vnd) * rules.lot_size
        if shares > 0:
            reason = "add" if held else "entry"
            orders.append(Order(day, symbol, "buy", shares, reason))
    return orders


def execute_orders(
    broker: PaperBroker,
    orders: list[Order],
    prices: pd.Series,
    session: pd.Timestamp,
    calendar: TradingCalendar,
) -> tuple[list[Trade], list[Order]]:
    """Fill orders at the close of ``session``, sells before buys.

    Args:
        broker: Account to trade.
        orders: Orders for this session.
        prices: Closes of ``session`` by symbol.
        session: Fill session.
        calendar: Trading calendar.

    Returns:
        The trades and the orders that could not be filled (no price,
        nothing settled, or no cash).
    """
    trades, unfilled = [], []
    ordered = sorted(orders, key=lambda order: order.side != "sell")
    for order in ordered:
        price = prices.get(order.symbol, math.nan)
        trade = None
        if price > 0 and order.side == "sell":
            trade = broker.sell(order.symbol, order.quantity, price,
                                session, calendar, order.reason)
        elif price > 0:
            trade = broker.buy(order.symbol, order.quantity, price,
                               session, order.reason)
        if trade is None:
            unfilled.append(order)
        else:
            trades.append(trade)
    return trades, unfilled
