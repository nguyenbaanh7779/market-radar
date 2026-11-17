"""Forward-test state: append-only CSV logs and the paper account.

The state folder is committed to the ``data`` branch after every run, so
each prediction carries a commit timestamp from before its outcome was
known. CSV keeps the git diffs readable.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from market_radar.calendar import TradingCalendar
from market_radar.config import TradingSettings
from market_radar.forecaster.labels import (
    CLASSES,
    PROBA_COLUMNS,
    classify_return,
)
from market_radar.trader.broker import PaperBroker
from market_radar.trader.strategy import Order

PREDICTION_KEY = ["asof_date", "symbol", "horizon", "model"]
LOGS = ("predictions", "resolved", "orders", "trades", "equity")


class ForwardState:
    """Files of the forward test under one folder.

    Args:
        root: State folder (created when first written).
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def path(self, name: str) -> Path:
        """Return the CSV file of a log.

        Args:
            name: One of :data:`LOGS`.

        Returns:
            Path of the log.
        """
        return self.root / f"{name}.csv"

    def read(self, name: str) -> pd.DataFrame:
        """Read a log.

        Args:
            name: Log name.

        Returns:
            Its rows (empty frame when the log does not exist yet).
        """
        path = self.path(name)
        if not path.is_file():
            return pd.DataFrame()
        return pd.read_csv(path, dtype={"symbol": str})

    def append(self, name: str, rows: pd.DataFrame,
               key: list[str] | None = None) -> int:
        """Append rows to a log, skipping keys that are already there.

        Args:
            name: Log name.
            rows: Rows to add.
            key: Columns identifying a row; None appends everything.

        Returns:
            Number of rows written.
        """
        if rows.empty:
            return 0
        rows = rows.copy()
        existing = self.read(name)
        if key and not existing.empty:
            seen = set(map(tuple, existing[key].astype(str).to_numpy()))
            fresh = [tuple(r) not in seen
                     for r in rows[key].astype(str).to_numpy()]
            rows = rows[fresh]
        if rows.empty:
            return 0
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.path(name)
        if existing.empty:
            rows.to_csv(path, index=False, float_format="%.6g")
        else:
            rows = rows.reindex(columns=existing.columns)
            rows.to_csv(path, mode="a", header=False, index=False,
                        float_format="%.6g")
        return len(rows)

    def load_account(
        self, rules: TradingSettings
    ) -> tuple[PaperBroker, dict[str, Any]]:
        """Load the paper account and its run metadata.

        Args:
            rules: Trading rules.

        Returns:
            The broker and a dict with ``started``, ``last_session`` and
            ``pending`` (orders not filled yet).
        """
        path = self.root / "account.json"
        if not path.is_file():
            meta = {"started": None, "last_session": None, "pending": []}
            return PaperBroker(rules.initial_capital_vnd, rules), meta
        data = json.loads(path.read_text(encoding="utf-8"))
        broker = PaperBroker.from_snapshot(data["broker"], rules)
        return broker, data["meta"]

    def save_account(self, broker: PaperBroker, meta: dict[str, Any]) -> None:
        """Save the paper account.

        Args:
            broker: Account to save.
            meta: Run metadata (see :meth:`load_account`).
        """
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {"broker": broker.snapshot(), "meta": meta}
        (self.root / "account.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def write_text(self, folder: str, asof: pd.Timestamp, suffix: str,
                   text: str) -> Path:
        """Write a dated text file (report or signal snapshot).

        Args:
            folder: Sub-folder, e.g. ``reports``.
            asof: Session the file describes.
            suffix: File extension including the dot.
            text: Content.

        Returns:
            The written path.
        """
        path = self.root / folder / f"{asof.date().isoformat()}{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


def resolve_predictions(
    predictions: pd.DataFrame,
    resolved: pd.DataFrame,
    closes: pd.DataFrame,
    calendar: TradingCalendar,
    band_pct: float,
) -> pd.DataFrame:
    """Score logged predictions whose target session has closed.

    The realised target is the ``h``-th realised session after the
    prediction date, so an unlisted holiday cannot shift the outcome.

    Args:
        predictions: The predictions log.
        resolved: The resolved log (rows there are skipped).
        closes: Closes, dates by symbols.
        calendar: Trading calendar with realised sessions.
        band_pct: Sideways band in percent.

    Returns:
        Newly resolved rows with the true label, return, hit and log loss.
    """
    if predictions.empty:
        return pd.DataFrame()
    todo = predictions.copy()
    if not resolved.empty:
        done = set(map(tuple, resolved[PREDICTION_KEY].astype(str)
                       .to_numpy()))
        keep = [tuple(r) not in done
                for r in todo[PREDICTION_KEY].astype(str).to_numpy()]
        todo = todo[keep]
    rows = []
    sessions = calendar.sessions
    for record in todo.itertuples(index=False):
        asof = pd.Timestamp(record.asof_date)
        later = sessions[sessions > asof]
        if len(later) < record.horizon or record.symbol not in closes:
            continue
        target = later[record.horizon - 1]
        start = closes[record.symbol].get(asof, np.nan)
        end = closes[record.symbol].get(target, np.nan)
        if not (start > 0 and end > 0):
            continue
        ret_pct = (end / start - 1.0) * 100.0
        truth = classify_return(pd.Series([ret_pct]), band_pct).iloc[0]
        proba = getattr(record, PROBA_COLUMNS[CLASSES.index(truth)])
        rows.append({
            "asof_date": record.asof_date,
            "symbol": record.symbol,
            "horizon": record.horizon,
            "model": record.model,
            "model_version": record.model_version,
            "target_date": target.date().isoformat(),
            "label_pred": record.label_pred,
            "label_true": truth,
            "fwd_ret_pct": ret_pct,
            "correct": record.label_pred == truth,
            "log_loss": float(-np.log(max(proba, 1e-12))),
            "resolved_at_utc": dt.datetime.now(dt.UTC).isoformat(
                timespec="seconds"),
        })
    return pd.DataFrame(rows)


def orders_to_records(orders: list[Order], planned_at: pd.Timestamp
                      ) -> pd.DataFrame:
    """Turn planned orders into log rows.

    Args:
        orders: Planned orders.
        planned_at: Session after whose close they were planned.

    Returns:
        One row per order.
    """
    return pd.DataFrame([
        {"planned_at": planned_at.date().isoformat(), **vars(order)}
        for order in orders
    ])
