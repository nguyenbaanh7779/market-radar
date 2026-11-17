"""Out-of-sample evaluation: walk-forward predictions, metrics, DM test."""

from __future__ import annotations

import logging
from collections.abc import Iterable

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import balanced_accuracy_score, f1_score

from market_radar.config import Settings
from market_radar.forecaster.labels import CLASSES, PROBA_COLUMNS
from market_radar.forecaster.models import make_model
from market_radar.forecaster.walk_forward import Fold

logger = logging.getLogger(__name__)
EPS = 1e-12


def walk_forward_predictions(
    panel: pd.DataFrame,
    feature_cols: list[str],
    horizon: int,
    model_names: Iterable[str],
    folds: list[Fold],
    settings: Settings,
) -> pd.DataFrame:
    """Fit every model on each fold and predict its test block.

    Args:
        panel: Features and labels (``label_<h>``) of every instrument.
        feature_cols: Feature columns.
        horizon: Label horizon.
        model_names: Models to evaluate.
        folds: Walk-forward folds.
        settings: Run settings.

    Returns:
        One row per test prediction: ``date``, ``symbol``, ``horizon``,
        ``model``, ``fold``, ``y_true`` and the class probabilities.
    """
    label = f"label_{horizon}"
    labelled = panel[panel[label].notna()]
    parts = []
    for fold in folds:
        train = labelled[labelled["date"].between(fold.train_start,
                                                  fold.train_end)]
        test = labelled[labelled["date"].between(fold.test_start,
                                                 fold.test_end)]
        if train.empty or test.empty:
            continue
        for name in model_names:
            model = make_model(name, settings, horizon, feature_cols)
            proba = model.fit(train, train[label]).predict_proba(test)
            part = test[["date", "symbol"]].copy()
            part["horizon"] = horizon
            part["model"] = name
            part["fold"] = fold.number
            part["y_true"] = test[label].to_numpy()
            parts.append(pd.concat([part, proba], axis=1))
        logger.info("h=%d fold %d/%d: train %d rows, test %d rows",
                    horizon, fold.number, len(folds), len(train), len(test))
    return pd.concat(parts, ignore_index=True)


def score_rows(oos: pd.DataFrame) -> pd.DataFrame:
    """Add the predicted label and per-row losses.

    Args:
        oos: Out-of-sample predictions with ``y_true`` and probabilities.

    Returns:
        A copy with ``y_pred``, ``correct``, ``log_loss`` and ``brier``.
    """
    out = oos.copy()
    proba = out[list(PROBA_COLUMNS)].to_numpy()
    truth = out["y_true"].map(CLASSES.index).to_numpy()
    onehot = np.eye(len(CLASSES))[truth]
    out["y_pred"] = np.asarray(CLASSES)[proba.argmax(axis=1)]
    out["correct"] = out["y_pred"] == out["y_true"]
    picked = proba[np.arange(len(out)), truth]
    out["log_loss"] = -np.log(np.clip(picked, EPS, 1.0))
    out["brier"] = ((proba - onehot) ** 2).sum(axis=1)
    return out


def classification_metrics(scored: pd.DataFrame) -> pd.Series:
    """Summarise scored predictions.

    Args:
        scored: Output of :func:`score_rows` for one model.

    Returns:
        Row count, accuracy, balanced accuracy, macro F1, mean log loss,
        mean Brier score and the share of each true class.
    """
    truth, pred = scored["y_true"], scored["y_pred"]
    shares = truth.value_counts(normalize=True).reindex(CLASSES,
                                                        fill_value=0.0)
    return pd.Series({
        "n": len(scored),
        "accuracy": scored["correct"].mean(),
        "balanced_accuracy": balanced_accuracy_score(truth, pred),
        "macro_f1": f1_score(truth, pred, labels=list(CLASSES),
                             average="macro", zero_division=0),
        "log_loss": scored["log_loss"].mean(),
        "brier": scored["brier"].mean(),
        "share_down": shares["DOWN"],
        "share_sideway": shares["SIDEWAY"],
        "share_up": shares["UP"],
    })


def metrics_table(scored: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Compute :func:`classification_metrics` per group.

    Args:
        scored: Scored predictions.
        by: Grouping columns, e.g. ``["horizon", "model"]``.

    Returns:
        One row per group.
    """
    rows = {
        key: classification_metrics(group)
        for key, group in scored.groupby(by, sort=True)
    }
    table = pd.DataFrame(rows).T
    table.index.names = by
    return table.reset_index()


def diebold_mariano(diff: pd.Series, lag: int) -> tuple[float, float]:
    """Diebold-Mariano test on a series of loss differences.

    Uses a Newey-West (Bartlett) long-run variance with ``lag`` lags.

    Args:
        diff: Loss of the candidate minus loss of the baseline, one value
            per session.
        lag: Number of autocovariance lags.

    Returns:
        The statistic (negative when the candidate has lower loss) and the
        two-sided p-value.
    """
    values = diff.dropna().to_numpy(dtype=float)
    n = values.size
    if n < 2:
        return float("nan"), float("nan")
    centred = values - values.mean()
    variance = centred @ centred / n
    for k in range(1, min(lag, n - 1) + 1):
        weight = 1.0 - k / (lag + 1.0)
        variance += 2.0 * weight * (centred[k:] @ centred[:-k]) / n
    if variance <= 0:
        return float("nan"), float("nan")
    stat = values.mean() / np.sqrt(variance / n)
    return float(stat), float(2.0 * stats.norm.sf(abs(stat)))


def significance_table(
    scored: pd.DataFrame,
    candidates: Iterable[str],
    baselines: Iterable[str],
    loss: str = "log_loss",
) -> pd.DataFrame:
    """Compare each candidate model with each baseline (DM test).

    Daily losses are averaged across instruments before testing, so the
    cross-sectional correlation within a session does not inflate the
    sample size.

    Args:
        scored: Scored predictions of several models and horizons.
        candidates: Models to test.
        baselines: Reference models.
        loss: Loss column, ``log_loss`` or ``brier``.

    Returns:
        One row per horizon, candidate and baseline with the mean daily
        loss difference, DM statistic and p-value.
    """
    daily = scored.pivot_table(index=["horizon", "date"], columns="model",
                               values=loss, aggfunc="mean")
    rows = []
    for horizon, frame in daily.groupby(level="horizon"):
        for candidate in candidates:
            for baseline in baselines:
                if {candidate, baseline} - set(frame.columns):
                    continue
                diff = frame[candidate] - frame[baseline]
                stat, p_value = diebold_mariano(diff, lag=int(horizon))
                rows.append({
                    "horizon": horizon, "candidate": candidate,
                    "baseline": baseline, "loss": loss,
                    "mean_diff": diff.mean(), "dm_stat": stat,
                    "p_value": p_value, "sessions": int(diff.notna().sum()),
                })
    return pd.DataFrame(rows)
