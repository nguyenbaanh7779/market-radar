import dataclasses
import json

import pandas as pd
import pytest

from market_radar import pipeline
from market_radar.data.store import BarStore
from market_radar.forward import ForwardState
from market_radar.report.telegram import split_message
from tests.conftest import make_bars

ALL = make_bars(sessions=430)
LAST = ALL["date"].max()


def store_bars(settings, bars):
    store = BarStore(settings.data_dir / "raw" / "bars")
    for symbol, frame in bars.groupby("symbol"):
        store.upsert(symbol, frame.drop(columns="symbol"), "test")


@pytest.fixture
def ready(settings, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("MARKET_RADAR_PORTFOLIO", raising=False)
    store_bars(settings, ALL[ALL["date"] < LAST])
    return settings


def run_daily(settings, today):
    return pipeline.daily(settings, settings.state_dir, today=today,
                          update=False, send=True)


def morning_after(session):
    """Local date of the run that should see ``session``'s bars."""
    return (session + pd.offsets.BDay(1)).date()


def test_daily_run_is_complete_and_idempotent(ready):
    asof = ALL["date"][ALL["date"] < LAST].max()
    today = morning_after(asof)
    first = run_daily(ready, today)
    assert first.asof == asof
    instruments = 2 + 1 + 6                             # indices, basket
    assert first.new_predictions == instruments * 2 * 4
    assert "MARKET RADAR" in first.report
    assert "GIAO DỊCH MÔ PHỎNG" in first.report          # default: vi
    assert "📌 TÓM TẮT" in first.report
    assert "Vì sao:" in first.report
    assert "Cách đọc bản tin: https://" in first.report
    state = ForwardState(ready.state_dir)
    predictions = state.read("predictions")
    assert set(predictions["horizon"]) == {1, 5}
    assert predictions["target_date"].min() > asof.date().isoformat()
    signals = json.loads(
        (ready.state_dir / "signals" / f"{asof.date()}.json").read_text())
    assert signals["asof"] == asof.date().isoformat()
    _, meta = state.load_account(ready.trading)
    assert meta["started"] == asof.date().isoformat()

    again = run_daily(ready, today)
    assert again.new_predictions == 0
    assert len(state.read("equity")) == 1


def test_next_session_resolves_and_trades(ready):
    asof = ALL["date"][ALL["date"] < LAST].max()
    run_daily(ready, morning_after(asof))
    store_bars(ready, ALL[ALL["date"] == LAST])
    outcome = run_daily(ready, morning_after(LAST))
    assert outcome.asof == LAST
    state = ForwardState(ready.state_dir)
    resolved = state.read("resolved")
    assert len(resolved) == 9 * 4                     # h=1 of every model
    assert set(resolved["horizon"]) == {1}
    assert resolved["target_date"].eq(LAST.date().isoformat()).all()
    equity = state.read("equity")
    assert list(equity["date"]) == [asof.date().isoformat(),
                                    LAST.date().isoformat()]
    trades = state.read("trades")
    if not trades.empty:
        assert (trades["session"] == LAST.date().isoformat()).all()
        assert (trades["quantity"] % 100 == 0).all()


def test_daily_waits_for_unpublished_data(ready):
    asof = ALL["date"][ALL["date"] < LAST].max()
    with pytest.raises(pipeline.DataNotReady):
        run_daily(ready, (asof + pd.Timedelta(days=9)).date())


def test_portfolio_section_only_in_sent_copy(ready, tmp_path, monkeypatch):
    path = tmp_path / "portfolio.yaml"
    path.write_text("holdings:\n  - {symbol: AAA, quantity: 100, "
                    "avg_price: 20}\n")
    monkeypatch.setenv("MARKET_RADAR_PORTFOLIO", str(path))
    asof = ALL["date"][ALL["date"] < LAST].max()
    outcome = run_daily(ready, morning_after(asof))
    assert "DANH MỤC CỦA BẠN" in outcome.report
    assert "DANH MỤC CỦA BẠN" not in outcome.report_path.read_text()


def test_english_newsletter(ready):
    settings = dataclasses.replace(
        ready, report=dataclasses.replace(ready.report, language="en"))
    asof = ALL["date"][ALL["date"] < LAST].max()
    outcome = run_daily(settings, morning_after(asof))
    assert "PAPER TRADING" in outcome.report
    assert "📌 SUMMARY" in outcome.report
    assert "GIAO DỊCH" not in outcome.report


def test_vietnamese_formatting():
    from market_radar.report import newsletter as n
    assert n.format_number(1234567.891, 2, "vi") == "1.234.567,89"
    assert n.format_percent(-0.5, 2, "vi") == "-0,50%"
    assert n.format_day("2026-11-16", "vi") == "16/11/2026"
    assert n.translate_term("lagging", "vi") == "tụt hậu"
    assert n.translate_text("BBB: weak technical signal, sector is lagging",
                            "vi") == ("BBB: tín hiệu kỹ thuật yếu, "
                                      "ngành đang tụt hậu")
    with pytest.raises(ValueError):
        n.render({}, language="fr")


def test_evaluate_and_backtest_write_results(ready):
    settings = dataclasses.replace(
        ready, models=dataclasses.replace(
            ready.models, candidates=("majority", "momentum", "logistic")))
    data = pipeline.load_market_data(settings)
    tables = pipeline.evaluate(settings, data)
    assert set(tables["metrics"]["model"]) == {"majority", "momentum",
                                               "logistic"}
    assert len(tables["significance"]) == 2 * 2         # 2 horizons
    result = pipeline.backtest(settings, data)
    assert not result.equity.empty
    out = pipeline.results_dir(settings)
    for name in ("wf_metrics.csv", "oos_predictions.parquet",
                 "backtest_summary.csv"):
        assert (out / name).is_file()


def test_split_message_respects_limit():
    text = "\n".join(f"line {i} " + "x" * 50 for i in range(200))
    chunks = split_message(text, limit=1000)
    assert all(len(chunk) <= 1000 for chunk in chunks)
    assert "".join(chunks) == text


def test_cli_exit_code_when_access_is_denied(monkeypatch, tmp_path):
    from market_radar import cli
    from market_radar.data.sources import SourceAccessDenied

    def denied(*args, **kwargs):
        raise SourceAccessDenied("HTTP 403")

    monkeypatch.setattr(pipeline, "update_data", denied)
    assert cli.main(["daily", "--state-dir", str(tmp_path)]) == 4
