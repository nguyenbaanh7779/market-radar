"""Simulated cash account: board lots, T+2 settlement, fees and tax.

Prices are in the units of the bars (thousand VND); cash is in VND.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping
from typing import Any

from market_radar.calendar import DateLike, TradingCalendar, to_day
from market_radar.config import TradingSettings


@dataclasses.dataclass
class Lot:
    """Shares bought in one fill.

    Attributes:
        quantity: Shares still held from this fill.
        price: Fill price per share (bar units).
        session: Fill session as ``YYYY-MM-DD``.
    """

    quantity: int
    price: float
    session: str


@dataclasses.dataclass(frozen=True)
class Trade:
    """An executed fill.

    Attributes:
        session: Fill session as ``YYYY-MM-DD``.
        symbol: Stock symbol.
        side: ``buy`` or ``sell``.
        quantity: Shares traded.
        price: Fill price per share (bar units).
        value_vnd: Traded value in VND.
        fee_vnd: Brokerage fee in VND.
        tax_vnd: Selling tax in VND.
        reason: Why the order was placed.
    """

    session: str
    symbol: str
    side: str
    quantity: int
    price: float
    value_vnd: float
    fee_vnd: float
    tax_vnd: float
    reason: str


class PaperBroker:
    """Cash account holding lots of shares.

    Args:
        cash_vnd: Starting cash in VND.
        rules: Lot size, settlement, fees and tax.
        lots: Existing positions by symbol (when restoring a snapshot).
    """

    def __init__(
        self,
        cash_vnd: float,
        rules: TradingSettings,
        lots: dict[str, list[Lot]] | None = None,
    ) -> None:
        self.cash_vnd = float(cash_vnd)
        self.rules = rules
        self.lots: dict[str, list[Lot]] = lots or {}

    def symbols(self) -> list[str]:
        """List the symbols currently held.

        Returns:
            Sorted symbols with a positive quantity.
        """
        return sorted(s for s, lots in self.lots.items() if lots)

    def quantity(self, symbol: str) -> int:
        """Return the shares held of a symbol.

        Args:
            symbol: Stock symbol.

        Returns:
            Total shares across lots.
        """
        return sum(lot.quantity for lot in self.lots.get(symbol, []))

    def avg_price(self, symbol: str) -> float:
        """Return the average cost per share of a holding.

        Args:
            symbol: Stock symbol.

        Returns:
            Quantity-weighted fill price, or NaN when not held.
        """
        lots = self.lots.get(symbol, [])
        shares = sum(lot.quantity for lot in lots)
        if shares == 0:
            return math.nan
        return sum(lot.quantity * lot.price for lot in lots) / shares

    def sellable(
        self,
        symbol: str,
        session: DateLike,
        calendar: TradingCalendar,
        ahead: int = 0,
    ) -> int:
        """Return the shares that have settled by a session.

        Shares bought on session ``b`` can be sold on session
        ``b + settlement_sessions``.

        Args:
            symbol: Stock symbol.
            session: Current realised session.
            calendar: Trading calendar.
            ahead: Sessions after ``session`` at which the sale would
                happen (1 when planning for the next session).

        Returns:
            Settled shares.
        """
        now = calendar.position(session) + ahead
        return sum(
            lot.quantity
            for lot in self.lots.get(symbol, [])
            if now - calendar.position(lot.session)
            >= self.rules.settlement_sessions
        )

    def equity_vnd(self, prices: Mapping[str, float]) -> float:
        """Value the account.

        Args:
            prices: Latest price per symbol (bar units).

        Returns:
            Cash plus the market value of every holding, in VND.
        """
        return self.cash_vnd + self.invested_vnd(prices)

    def invested_vnd(self, prices: Mapping[str, float]) -> float:
        """Value the holdings.

        Args:
            prices: Latest price per symbol (bar units).

        Returns:
            Market value of every holding, in VND.
        """
        unit = self.rules.price_unit_vnd
        return sum(self.quantity(s) * prices[s] * unit for s in self.symbols())

    def buy(
        self,
        symbol: str,
        quantity: int,
        price: float,
        session: DateLike,
        reason: str,
    ) -> Trade | None:
        """Buy whole lots, as many as cash allows up to ``quantity``.

        Args:
            symbol: Stock symbol.
            quantity: Shares wanted.
            price: Fill price (bar units).
            session: Fill session.
            reason: Why the order was placed.

        Returns:
            The trade, or None if not even one lot is affordable.
        """
        lot_cost = self._value(self.rules.lot_size, price) * (
            1.0 + self.rules.buy_fee_pct / 100.0)
        affordable = int(self.cash_vnd // lot_cost) * self.rules.lot_size
        shares = min(self._whole_lots(quantity), affordable)
        if shares <= 0:
            return None
        value = self._value(shares, price)
        fee = value * self.rules.buy_fee_pct / 100.0
        self.cash_vnd -= value + fee
        day = to_day(session).date().isoformat()
        self.lots.setdefault(symbol, []).append(Lot(shares, price, day))
        return Trade(day, symbol, "buy", shares, price, value, fee, 0.0,
                     reason)

    def sell(
        self,
        symbol: str,
        quantity: int,
        price: float,
        session: DateLike,
        calendar: TradingCalendar,
        reason: str,
    ) -> Trade | None:
        """Sell settled shares, oldest lots first.

        Args:
            symbol: Stock symbol.
            quantity: Shares wanted.
            price: Fill price (bar units).
            session: Fill session.
            calendar: Trading calendar (for settlement).
            reason: Why the order was placed.

        Returns:
            The trade, or None if nothing settled can be sold.
        """
        shares = min(quantity, self.sellable(symbol, session, calendar))
        if shares <= 0:
            return None
        remaining = shares
        for lot in self.lots[symbol]:
            taken = min(lot.quantity, remaining)
            lot.quantity -= taken
            remaining -= taken
            if remaining == 0:
                break
        self.lots[symbol] = [lot for lot in self.lots[symbol] if lot.quantity]
        value = self._value(shares, price)
        fee = value * self.rules.sell_fee_pct / 100.0
        tax = value * self.rules.sell_tax_pct / 100.0
        self.cash_vnd += value - fee - tax
        day = to_day(session).date().isoformat()
        return Trade(day, symbol, "sell", shares, price, value, fee, tax,
                     reason)

    def snapshot(self) -> dict[str, Any]:
        """Serialise the account.

        Returns:
            JSON-ready cash and lots.
        """
        return {
            "cash_vnd": self.cash_vnd,
            "lots": {
                symbol: [dataclasses.asdict(lot) for lot in lots]
                for symbol, lots in self.lots.items() if lots
            },
        }

    @classmethod
    def from_snapshot(
        cls, data: Mapping[str, Any], rules: TradingSettings
    ) -> PaperBroker:
        """Restore an account saved with :meth:`snapshot`.

        Args:
            data: Saved snapshot.
            rules: Trading rules.

        Returns:
            The restored broker.
        """
        lots = {
            symbol: [Lot(**lot) for lot in items]
            for symbol, items in data.get("lots", {}).items()
        }
        return cls(data["cash_vnd"], rules, lots)

    def _value(self, shares: int, price: float) -> float:
        """Convert shares at a price to VND.

        Args:
            shares: Number of shares.
            price: Price in bar units.

        Returns:
            Value in VND.
        """
        return shares * price * self.rules.price_unit_vnd

    def _whole_lots(self, quantity: int) -> int:
        """Round a share count down to whole board lots.

        Args:
            quantity: Shares.

        Returns:
            The largest multiple of the lot size not above ``quantity``.
        """
        return (quantity // self.rules.lot_size) * self.rules.lot_size
