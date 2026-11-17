"""Direction models behind one interface: baselines, logistic, GBDT."""

from __future__ import annotations

import abc
import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from market_radar.config import Settings
from market_radar.forecaster.labels import (
    CLASSES,
    PROBA_COLUMNS,
    classify_return,
)

logger = logging.getLogger(__name__)
SMOOTHING = 1.0


class DirectionModel(abc.ABC):
    """Predicts P(DOWN), P(SIDEWAY), P(UP) for each row of features.

    Args:
        feature_cols: Feature columns the model uses.
    """

    name = "base"

    def __init__(self, feature_cols: list[str]) -> None:
        self.feature_cols = list(feature_cols)

    @abc.abstractmethod
    def fit(self, features: pd.DataFrame, labels: pd.Series) -> DirectionModel:
        """Fit the model.

        Args:
            features: Training rows.
            labels: Direction labels of those rows.

        Returns:
            The fitted model.
        """

    @abc.abstractmethod
    def predict_proba(self, features: pd.DataFrame) -> pd.DataFrame:
        """Predict class probabilities.

        Args:
            features: Rows to predict.

        Returns:
            Columns ``p_down``, ``p_sideway``, ``p_up`` summing to one.
        """

    def explain(self, features: pd.DataFrame, top: int = 3) -> pd.Series:
        """Describe what drives each prediction.

        Args:
            features: Rows to explain.
            top: Number of drivers to list.

        Returns:
            One text per row (empty when the model has no explanation).
        """
        return pd.Series("", index=features.index, dtype="object")


class MajorityModel(DirectionModel):
    """Baseline: always the class frequencies of the training window."""

    name = "majority"

    def fit(self, features: pd.DataFrame, labels: pd.Series) -> DirectionModel:
        """Store the smoothed class frequencies.

        Args:
            features: Training rows (unused).
            labels: Direction labels.

        Returns:
            The fitted model.
        """
        counts = labels.value_counts().reindex(CLASSES, fill_value=0)
        self._proba = _smooth(counts.to_numpy(dtype=float))
        return self

    def predict_proba(self, features: pd.DataFrame) -> pd.DataFrame:
        """Repeat the training frequencies for every row.

        Args:
            features: Rows to predict.

        Returns:
            Constant probabilities.
        """
        values = np.tile(self._proba, (len(features), 1))
        return pd.DataFrame(values, index=features.index,
                            columns=PROBA_COLUMNS)


class MomentumModel(DirectionModel):
    """Baseline: P(next direction | direction of the past ``h`` sessions).

    Args:
        feature_cols: Feature columns (must contain ``ret_<h>``).
        horizon: Look-back equal to the forecast horizon.
        band_pct: Sideways band used to bucket past returns.
    """

    name = "momentum"

    def __init__(self, feature_cols: list[str], horizon: int,
                 band_pct: float) -> None:
        super().__init__(feature_cols)
        self._column = f"ret_{horizon}"
        self._band = band_pct

    def fit(self, features: pd.DataFrame, labels: pd.Series) -> DirectionModel:
        """Estimate smoothed conditional class frequencies.

        Args:
            features: Training rows with ``ret_<h>``.
            labels: Direction labels.

        Returns:
            The fitted model.
        """
        bucket = self._bucket(features)
        table = pd.crosstab(bucket, labels).reindex(
            index=list(CLASSES), columns=list(CLASSES), fill_value=0)
        self._table = {
            past: _smooth(row.to_numpy(dtype=float))
            for past, row in table.iterrows()
        }
        counts = labels.value_counts().reindex(CLASSES, fill_value=0)
        self._marginal = _smooth(counts.to_numpy(dtype=float))
        return self

    def predict_proba(self, features: pd.DataFrame) -> pd.DataFrame:
        """Look up the conditional frequencies of each row's bucket.

        Args:
            features: Rows to predict.

        Returns:
            Probabilities per row.
        """
        bucket = self._bucket(features)
        values = [self._table.get(past, self._marginal) for past in bucket]
        return pd.DataFrame(np.vstack(values) if values else
                            np.empty((0, 3)), index=features.index,
                            columns=PROBA_COLUMNS)

    def _bucket(self, features: pd.DataFrame) -> pd.Series:
        """Bucket past returns into direction labels.

        Args:
            features: Rows with ``ret_<h>`` (a fraction).

        Returns:
            Past direction per row (None when unknown).
        """
        return classify_return(features[self._column] * 100.0, self._band)


class LogisticModel(DirectionModel):
    """Multinomial logistic regression on imputed, standardised features.

    Args:
        feature_cols: Feature columns.
        params: Keyword arguments for ``LogisticRegression``.
    """

    name = "logistic"

    def __init__(self, feature_cols: list[str],
                 params: dict[str, Any]) -> None:
        super().__init__(feature_cols)
        self._pipeline = Pipeline([
            ("impute", SimpleImputer(strategy="median",
                                     keep_empty_features=True)),
            ("scale", StandardScaler()),
            ("model", LogisticRegression(**params)),
        ])

    def fit(self, features: pd.DataFrame, labels: pd.Series) -> DirectionModel:
        """Fit the pipeline.

        Args:
            features: Training rows.
            labels: Direction labels.

        Returns:
            The fitted model.
        """
        self._pipeline.fit(features[self.feature_cols], labels.astype(str))
        return self

    def predict_proba(self, features: pd.DataFrame) -> pd.DataFrame:
        """Predict probabilities.

        Args:
            features: Rows to predict.

        Returns:
            Probabilities per row.
        """
        raw = self._pipeline.predict_proba(features[self.feature_cols])
        return _align(raw, self._pipeline.classes_, features.index)

    def explain(self, features: pd.DataFrame, top: int = 3) -> pd.Series:
        """List the features pushing hardest towards the predicted class.

        A feature's push is its coefficient for that class times its
        standardised value.

        Args:
            features: Rows to explain.
            top: Number of drivers to list.

        Returns:
            Text such as ``rsi_14 +0.42, ret_5 +0.31`` per row.
        """
        if features.empty:
            return super().explain(features, top)
        scaled = self._pipeline[:-1].transform(features[self.feature_cols])
        model = self._pipeline[-1]
        winners = model.predict_proba(scaled).argmax(axis=1)
        pushes = model.coef_[winners] * scaled
        return pd.Series(
            [_top_drivers(row, self.feature_cols, top) for row in pushes],
            index=features.index, dtype="object")


class GBDTModel(DirectionModel):
    """Gradient-boosted trees: LightGBM, or scikit-learn's HistGB fallback.

    Args:
        feature_cols: Feature columns.
        params: LightGBM keyword arguments.
    """

    name = "gbdt"

    def __init__(self, feature_cols: list[str],
                 params: dict[str, Any]) -> None:
        super().__init__(feature_cols)
        try:
            import lightgbm
        except (ImportError, OSError) as error:  # missing libomp on macOS
            from sklearn.ensemble import HistGradientBoostingClassifier
            logger.warning("LightGBM unavailable (%s); using HistGB", error)
            self._model = HistGradientBoostingClassifier(
                learning_rate=params.get("learning_rate", 0.05),
                max_iter=params.get("n_estimators", 300),
                max_leaf_nodes=params.get("num_leaves", 15),
                min_samples_leaf=params.get("min_child_samples", 200),
                random_state=7,
            )
            self._is_lgbm = False
        else:
            self._model = lightgbm.LGBMClassifier(
                objective="multiclass", random_state=7, verbose=-1,
                **params)
            self._is_lgbm = True

    def fit(self, features: pd.DataFrame, labels: pd.Series) -> DirectionModel:
        """Fit the trees.

        Args:
            features: Training rows.
            labels: Direction labels.

        Returns:
            The fitted model.
        """
        self._model.fit(features[self.feature_cols], labels.astype(str))
        return self

    def predict_proba(self, features: pd.DataFrame) -> pd.DataFrame:
        """Predict probabilities.

        Args:
            features: Rows to predict.

        Returns:
            Probabilities per row.
        """
        raw = self._model.predict_proba(features[self.feature_cols])
        return _align(raw, self._model.classes_, features.index)

    def explain(self, features: pd.DataFrame, top: int = 3) -> pd.Series:
        """List the largest SHAP contributions to the predicted class.

        Uses LightGBM's built-in TreeSHAP (``pred_contrib``); the HistGB
        fallback has no explanation.

        Args:
            features: Rows to explain.
            top: Number of drivers to list.

        Returns:
            Text such as ``vol_20 +0.12, ret_1 -0.08`` per row.
        """
        if not self._is_lgbm or features.empty:
            return super().explain(features, top)
        data = features[self.feature_cols]
        winners = self._model.predict_proba(data).argmax(axis=1)
        contrib = self._model.predict(data, pred_contrib=True)
        width = len(self.feature_cols) + 1
        rows = [
            contrib[i, k * width:(k + 1) * width - 1]
            for i, k in enumerate(winners)
        ]
        return pd.Series(
            [_top_drivers(row, self.feature_cols, top) for row in rows],
            index=features.index, dtype="object")


def make_model(
    name: str, settings: Settings, horizon: int, feature_cols: list[str]
) -> DirectionModel:
    """Create an unfitted model by name.

    Args:
        name: ``majority``, ``momentum``, ``logistic`` or ``gbdt``.
        settings: Run settings (hyperparameters, band).
        horizon: Forecast horizon in sessions.
        feature_cols: Feature columns.

    Returns:
        The model.

    Raises:
        ValueError: For an unknown name.
    """
    if name == "majority":
        return MajorityModel(feature_cols)
    if name == "momentum":
        return MomentumModel(feature_cols, horizon,
                             settings.labels.sideway_band_pct)
    if name == "logistic":
        return LogisticModel(feature_cols, settings.models.logistic)
    if name == "gbdt":
        return GBDTModel(feature_cols, settings.models.gbdt)
    raise ValueError(f"Unknown model: {name!r}")


def _smooth(counts: np.ndarray) -> np.ndarray:
    """Turn class counts into Laplace-smoothed probabilities.

    Args:
        counts: Count per class in :data:`CLASSES` order.

    Returns:
        Probabilities summing to one.
    """
    return (counts + SMOOTHING) / (counts.sum() + SMOOTHING * len(counts))


def _align(
    raw: np.ndarray, classes: np.ndarray, index: pd.Index
) -> pd.DataFrame:
    """Put probabilities in :data:`CLASSES` order, zero for unseen classes.

    Args:
        raw: Probabilities in the model's class order.
        classes: Classes the model was fitted on.
        index: Row index of the output.

    Returns:
        Columns ``p_down``, ``p_sideway``, ``p_up``.
    """
    out = np.zeros((raw.shape[0], len(CLASSES)))
    for j, label in enumerate(classes):
        out[:, CLASSES.index(str(label))] = raw[:, j]
    return pd.DataFrame(out, index=index, columns=PROBA_COLUMNS)


def _top_drivers(values: np.ndarray, names: list[str], top: int) -> str:
    """Format the largest positive contributions.

    Args:
        values: Contribution per feature.
        names: Feature names.
        top: How many to keep.

    Returns:
        Comma-separated ``name +value`` items.
    """
    order = np.argsort(values)[::-1][:top]
    return ", ".join(f"{names[i]} {values[i]:+.2f}" for i in order)
