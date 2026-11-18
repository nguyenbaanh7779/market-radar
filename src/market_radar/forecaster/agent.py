"""Forecasting agents: the common interface of proposal section 6.5.

Every agent takes data up to session ``t`` and returns, per instrument,
a direction label, class probabilities and an explanation. Specialised
agents (technical, money flow, fundamentals, per sector) and a combiner
can be added later behind the same interface.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd

from market_radar.config import Settings
from market_radar.forecaster.labels import CLASSES, PROBA_COLUMNS
from market_radar.forecaster.models import DirectionModel, make_model


@dataclasses.dataclass
class ForecastAgent:
    """A direction model for one horizon, fitted on all labelled history.

    Attributes:
        model_name: Name understood by :func:`make_model`.
        horizon: Forecast horizon in sessions.
        feature_cols: Feature columns used.
        settings: Run settings.
    """

    model_name: str
    horizon: int
    feature_cols: list[str]
    settings: Settings
    model: DirectionModel | None = None

    @property
    def version(self) -> str:
        """Return a version string tied to the settings that matter.

        A fallback backend (e.g. HistGB instead of LightGBM) is part of the
        name, so forward logs never mix two different models.
        """
        name = self.model_name
        if self.model is not None and self.model.backend == "histgb":
            name += "-histgb"
        return f"{name}-h{self.horizon}-{self.settings.fingerprint()}"

    def fit(self, panel: pd.DataFrame) -> ForecastAgent:
        """Fit on every labelled row from the sample start onwards.

        Args:
            panel: Features and labels; rows whose label is still unknown
                (the last ``h`` sessions) are ignored.

        Returns:
            The fitted agent.
        """
        label = f"label_{self.horizon}"
        start = pd.Timestamp(self.settings.data.sample_start)
        train = panel[(panel["date"] >= start) & panel[label].notna()]
        self.model = make_model(self.model_name, self.settings,
                                self.horizon, self.feature_cols)
        self.model.fit(train, train[label])
        return self

    def predict(self, rows: pd.DataFrame) -> pd.DataFrame:
        """Forecast the given rows (typically one session).

        Args:
            rows: Feature rows with ``date`` and ``symbol``.

        Returns:
            ``symbol``, ``asof_date``, ``horizon``, ``model``,
            ``model_version``, the probabilities, ``label_pred`` and
            ``explanation``.

        Raises:
            RuntimeError: If called before :meth:`fit`.
        """
        if self.model is None:
            raise RuntimeError("Call fit() before predict()")
        proba = self.model.predict_proba(rows)
        out = pd.DataFrame({
            "symbol": rows["symbol"].to_numpy(),
            "asof_date": rows["date"].to_numpy(),
            "horizon": self.horizon,
            "model": self.model_name,
            "model_version": self.version,
        }, index=rows.index)
        out = pd.concat([out, proba], axis=1)
        winners = proba[list(PROBA_COLUMNS)].to_numpy().argmax(axis=1)
        out["label_pred"] = np.asarray(CLASSES)[winners]
        out["explanation"] = self.model.explain(rows)
        return out.reset_index(drop=True)
