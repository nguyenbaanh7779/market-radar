"""Performance metrics of an equity curve."""

from __future__ import annotations

import numpy as np
import pandas as pd

PERIODS_PER_YEAR = 252


def performance_metrics(equity: pd.Series) -> dict[str, float]:
    """Return, risk and drawdown of an equity curve.

    Args:
        equity: Account value per session.

    Returns:
        Total return, CAGR and annualised volatility (percent), Sharpe and
        Sortino ratios (zero risk-free rate), maximum drawdown (percent)
        and the Calmar ratio.
    """
    equity = equity.dropna()
    returns = equity.pct_change().dropna()
    years = max(len(returns) / PERIODS_PER_YEAR, 1e-9)
    total = equity.iloc[-1] / equity.iloc[0] - 1.0
    cagr = (1.0 + total) ** (1.0 / years) - 1.0
    vol = returns.std(ddof=1) * np.sqrt(PERIODS_PER_YEAR)
    downside = returns[returns < 0].std(ddof=1) * np.sqrt(PERIODS_PER_YEAR)
    drawdown = (equity / equity.cummax() - 1.0).min()
    mean = returns.mean() * PERIODS_PER_YEAR
    return {
        "total_return_pct": 100.0 * total,
        "cagr_pct": 100.0 * cagr,
        "ann_vol_pct": 100.0 * vol,
        "sharpe": mean / vol if vol > 0 else np.nan,
        "sortino": mean / downside if downside > 0 else np.nan,
        "max_drawdown_pct": 100.0 * drawdown,
        "calmar": cagr / abs(drawdown) if drawdown < 0 else np.nan,
    }


def trading_metrics(
    trades: pd.DataFrame, equity: pd.Series
) -> dict[str, float]:
    """Activity and cost of a trade list.

    Args:
        trades: Trades with ``value_vnd``, ``fee_vnd`` and ``tax_vnd``.
        equity: Account value per session.

    Returns:
        Trade count, annualised turnover (traded value over average
        equity per year) and total fees and taxes in VND.
    """
    years = max(len(equity) / PERIODS_PER_YEAR, 1e-9)
    traded = trades["value_vnd"].sum() if not trades.empty else 0.0
    return {
        "trades": float(len(trades)),
        "turnover_per_year": traded / equity.mean() / years,
        "fees_vnd": float(trades["fee_vnd"].sum()) if len(trades) else 0.0,
        "taxes_vnd": float(trades["tax_vnd"].sum()) if len(trades) else 0.0,
    }
