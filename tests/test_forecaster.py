import numpy as np
import pandas as pd
import pytest

from market_radar.dataset import assemble
from market_radar.forecaster.agent import ForecastAgent
from market_radar.forecaster.evaluate import (
    diebold_mariano,
    metrics_table,
    score_rows,
    significance_table,
    walk_forward_predictions,
)
from market_radar.forecaster.labels import (
    PROBA_COLUMNS,
    add_labels,
    classify_return,
)
from market_radar.forecaster.models import make_model
from market_radar.forecaster.walk_forward import walk_forward_folds
from tests.conftest import make_bars


def test_classify_return_band():
    ret = pd.Series([0.5, -0.5, 0.2, -0.2, 0.0, None])
    assert classify_return(ret, 0.2).tolist() == [
        "UP", "DOWN", "SIDEWAY", "SIDEWAY", "SIDEWAY", None]


def test_labels_look_exactly_h_sessions_ahead():
    dates = pd.bdate_range("2026-01-05", periods=5)
    panel = pd.DataFrame({"symbol": "AAA", "date": dates,
                          "close": [10.0, 10.1, 10.0, 10.5, 10.5]})
    out = add_labels(panel, (1, 2), 0.2)
    assert out["label_1"].tolist() == ["UP", "DOWN", "UP", "SIDEWAY", None]
    assert out["fwd_ret_2"].round(6).tolist()[:3] == [0.0, 3.960396, 5.0]
    assert out["label_2"].tolist()[-2:] == [None, None]


def test_suspect_moves_invalidate_overlapping_labels():
    dates = pd.bdate_range("2026-01-05", periods=6)
    panel = pd.DataFrame({"symbol": "AAA", "date": dates,
                          "close": [10.0, 10.0, 7.0, 7.0, 7.0, 7.0]})
    suspect = pd.DataFrame({"symbol": ["AAA"], "date": [dates[2]]})
    out = add_labels(panel, (1, 2), 0.2, suspect)
    # the jump happens on day 3: windows (t, t+h] containing it are void
    assert out["label_1"].isna().tolist() == [
        False, True, False, False, False, True]
    assert out["label_2"].isna().tolist() == [
        True, True, False, False, True, True]


def test_features_are_point_in_time(settings):
    bars = make_bars()
    cutoff = bars["date"].unique()[300]
    changed = bars.copy()
    later = changed["date"] > cutoff
    noise = np.random.default_rng(3).uniform(0.8, 1.2, later.sum())
    for column in ("open", "high", "low", "close"):
        changed.loc[later, column] = changed.loc[later, column] * noise
    before = assemble(bars, settings)
    after = assemble(changed, settings)
    cols = before.feature_cols
    left = before.panel[before.panel["date"] <= cutoff]
    right = after.panel[after.panel["date"] <= cutoff]
    pd.testing.assert_frame_equal(
        left[["symbol", "date", *cols]].reset_index(drop=True),
        right[["symbol", "date", *cols]].reset_index(drop=True))


def test_assemble_adds_basket_and_drops_volume_features(settings):
    data = assemble(make_bars(with_volume=False), settings)
    assert "BANKS" in data.panel["symbol"].unique()
    assert not data.has_volume
    assert "vol_ratio_20" not in data.feature_cols
    assert "liquidity_ratio" not in data.feature_cols
    assert "sec_rs_ratio" in data.feature_cols
    banks = data.panel[data.panel["symbol"] == "BANKS"]
    assert banks["is_index"].eq(1.0).all()


def test_walk_forward_folds_purge_and_embargo():
    sessions = pd.bdate_range("2023-01-02", periods=300)
    folds = walk_forward_folds(sessions, min_train=100, test_size=50,
                               horizon=5, embargo=3)
    assert folds[0].test_start == sessions[108]
    position = {day: i for i, day in enumerate(sessions)}
    for fold in folds:
        gap = position[fold.test_start] - position[fold.train_end]
        assert gap == 5 + 3 + 1
        assert position[fold.train_end] + 1 >= 100
    tests = [(f.test_start, f.test_end) for f in folds]
    assert all(a[1] < b[0] for a, b in zip(tests, tests[1:], strict=False))
    assert folds[-1].test_end == sessions[-1]


@pytest.fixture
def data(settings):
    return assemble(make_bars(), settings)


@pytest.mark.parametrize("name", ["majority", "momentum", "logistic",
                                  "gbdt"])
def test_models_return_valid_probabilities(settings, data, name):
    train = data.panel.dropna(subset=["label_1"])
    model = make_model(name, settings, 1, data.feature_cols)
    proba = model.fit(train, train["label_1"]).predict_proba(train.head(50))
    assert list(proba.columns) == list(PROBA_COLUMNS)
    assert np.allclose(proba.sum(axis=1), 1.0)
    explained = model.explain(train.head(3))
    assert len(explained) == 3
    if name in ("logistic", "gbdt"):
        assert explained.str.len().gt(0).all()


def test_missing_class_gets_zero_probability(settings, data):
    train = data.panel.dropna(subset=["label_1"])
    train = train[train["label_1"] != "SIDEWAY"]
    model = make_model("logistic", settings, 1, data.feature_cols)
    proba = model.fit(train, train["label_1"]).predict_proba(train.head(5))
    assert (proba["p_sideway"] == 0).all()


def test_walk_forward_evaluation_and_metrics(settings, data):
    sessions = data.calendar.sessions
    sessions = sessions[sessions >= pd.Timestamp(
        settings.data.sample_start)]
    folds = walk_forward_folds(sessions, 120, 40, 1, 2)
    oos = walk_forward_predictions(data.panel, data.feature_cols, 1,
                                   ["majority", "logistic"], folds,
                                   settings)
    assert set(oos["fold"]) == {f.number for f in folds}
    assert oos["date"].min() == folds[0].test_start
    scored = score_rows(oos)
    table = metrics_table(scored, ["horizon", "model"])
    assert set(table["model"]) == {"majority", "logistic"}
    assert table["accuracy"].between(0, 1).all()
    sig = significance_table(scored, ["logistic"], ["majority"])
    assert len(sig) == 1 and 0 <= sig["p_value"].iloc[0] <= 1


def test_diebold_mariano_detects_a_clear_difference():
    rng = np.random.default_rng(5)
    better = pd.Series(rng.normal(-0.05, 0.05, 400))
    stat, p_value = diebold_mariano(better, lag=1)
    assert stat < 0 and p_value < 0.01
    assert np.isnan(diebold_mariano(pd.Series([1.0]), lag=1)[0])


def test_agent_predicts_last_session(settings, data):
    agent = ForecastAgent("logistic", 5, data.feature_cols, settings)
    rows = data.panel[data.panel["date"] == data.asof]
    out = agent.fit(data.panel).predict(rows)
    assert len(out) == rows["symbol"].nunique()
    assert out["model_version"].str.startswith("logistic-h5-").all()
    assert set(out["label_pred"]) <= {"UP", "DOWN", "SIDEWAY"}
