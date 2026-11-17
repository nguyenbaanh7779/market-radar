"""Command-line interface: ``market-radar <command>``."""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from pathlib import Path

import pandas as pd

from market_radar import __version__, pipeline
from market_radar.config import Settings, load_settings
from market_radar.data.quality import quality_report
from market_radar.signals.tickers import ticker_flags

logger = logging.getLogger("market_radar")
EXIT_DATA_NOT_READY = 3


def build_parser() -> argparse.ArgumentParser:
    """Define the commands and their options.

    Returns:
        The argument parser.
    """
    parser = argparse.ArgumentParser(
        prog="market-radar",
        description="VN stock signals, direction forecasts and paper "
                    "trading.")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="debug logging")
    commands = parser.add_subparsers(dest="command", required=True)

    update = commands.add_parser("update", help="download new daily bars")
    update.add_argument("--symbols", type=_symbols,
                        help="comma-separated symbols (default: universe)")
    update.add_argument("--start", type=dt.date.fromisoformat,
                        help="first date for symbols without bars")
    update.add_argument("--source", choices=["arena", "vnstock"],
                        help="override data.source")

    commands.add_parser("check", help="data-quality report")
    commands.add_parser("signals", help="market, sector and ticker "
                                        "signals of the latest session")

    evaluate = commands.add_parser("evaluate",
                                   help="walk-forward model evaluation")
    evaluate.add_argument("--horizons", type=_ints,
                          help="comma-separated horizons (default: all)")
    evaluate.add_argument("--models", type=_symbols_lower,
                          help="comma-separated models (default: all)")

    commands.add_parser("backtest", help="paper-trade the out-of-sample "
                                         "forecasts against VN30")

    daily = commands.add_parser("daily", help="run the agent once")
    daily.add_argument("--state-dir", type=Path,
                       help="forward-test state folder (default: state/)")
    daily.add_argument("--today", type=dt.date.fromisoformat,
                       help="local run date (default: today)")
    daily.add_argument("--no-update", action="store_true",
                       help="use the stored bars as they are")
    daily.add_argument("--send", action="store_true",
                       help="send the newsletter to Telegram")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Arguments (default: ``sys.argv[1:]``).

    Returns:
        Process exit code (3 when the data is not published yet).
    """
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr)
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 20)
    settings = load_settings()
    try:
        return COMMANDS[args.command](settings, args)
    except pipeline.DataNotReady as error:
        logger.warning("%s", error)
        return EXIT_DATA_NOT_READY


def cmd_update(settings: Settings, args: argparse.Namespace) -> int:
    """Download bars and print the update report.

    Args:
        settings: Run settings.
        args: Parsed arguments.

    Returns:
        0 when every symbol updated, 1 when some failed.
    """
    report = pipeline.update_data(settings, args.symbols, args.start,
                                  args.source)
    print(report.to_string(index=False))
    failed = report[report["status"] != "ok"]
    if not failed.empty:
        print(f"\n{len(failed)} symbols without data: "
              f"{', '.join(failed['symbol'])}")
    return 0 if failed.empty else 1


def cmd_check(settings: Settings, args: argparse.Namespace) -> int:
    """Print the data-quality report and suspect moves.

    Args:
        settings: Run settings.
        args: Parsed arguments (unused).

    Returns:
        0.
    """
    data = pipeline.load_market_data(settings)
    raw = data.bars[data.bars["source"] != "basket"]
    report = quality_report(raw, data.calendar.sessions, settings.universe)
    print(report.to_string(index=False))
    print(f"\nSessions: {data.calendar.sessions[0].date()} to "
          f"{data.asof.date()} ({len(data.calendar.sessions)})")
    print(f"Volume available: {data.has_volume}")
    print(f"Moves beyond the price limit ({len(data.suspect)}):")
    print(data.suspect.tail(20).to_string(index=False))
    return 0


def cmd_signals(settings: Settings, args: argparse.Namespace) -> int:
    """Print the Module 1 signals of the latest session.

    Args:
        settings: Run settings.
        args: Parsed arguments (unused).

    Returns:
        0.
    """
    data = pipeline.load_market_data(settings)
    asof = data.asof
    print(f"Market state on {asof.date()}:")
    print(data.market.loc[asof].to_string())
    rotation = data.rotation[data.rotation["date"] == asof]
    print("\nSector rotation:")
    print(rotation.drop(columns="date").to_string(index=False))
    rows = data.panel[(data.panel["date"] == asof)
                      & data.panel["symbol"].isin(settings.universe.stocks)]
    flags = ticker_flags(rows.set_index("symbol"), settings.signals)
    flagged = flags[flags["flag"] != "neutral"].sort_values("flag")
    print("\nTicker flags:")
    print(flagged.to_string())
    return 0


def cmd_evaluate(settings: Settings, args: argparse.Namespace) -> int:
    """Run walk-forward validation and print the tables.

    Args:
        settings: Run settings.
        args: Parsed arguments.

    Returns:
        0.
    """
    data = pipeline.load_market_data(settings)
    horizons = tuple(args.horizons) if args.horizons else None
    models = tuple(args.models) if args.models else None
    tables = pipeline.evaluate(settings, data, horizons, models)
    print("Out-of-sample metrics:")
    print(tables["metrics"].round(4).to_string(index=False))
    print("\nDiebold-Mariano test on daily log loss "
          "(negative statistic = candidate better):")
    print(tables["significance"].round(4).to_string(index=False))
    print(f"\nSaved to {pipeline.results_dir(settings)}")
    return 0


def cmd_backtest(settings: Settings, args: argparse.Namespace) -> int:
    """Backtest the trading rules and print the summary.

    Args:
        settings: Run settings.
        args: Parsed arguments (unused).

    Returns:
        0.
    """
    data = pipeline.load_market_data(settings)
    result = pipeline.backtest(settings, data)
    equity = result.equity
    print(f"Backtest {equity['date'].min().date()} to "
          f"{equity['date'].max().date()} "
          f"({settings.models.primary}, h={settings.trading.horizon}):")
    print(result.summary().round(3).to_string())
    print(f"\nSaved to {pipeline.results_dir(settings)}")
    return 0


def cmd_daily(settings: Settings, args: argparse.Namespace) -> int:
    """Run the agent once and print the newsletter.

    Args:
        settings: Run settings.
        args: Parsed arguments.

    Returns:
        0.
    """
    outcome = pipeline.daily(
        settings, args.state_dir or settings.state_dir, args.today,
        update=not args.no_update, send=args.send)
    print(outcome.report)
    print(f"[{outcome.new_predictions} new predictions, "
          f"{outcome.resolved} resolved, {outcome.sent} messages sent; "
          f"report saved to {outcome.report_path}]")
    return 0


COMMANDS = {
    "update": cmd_update,
    "check": cmd_check,
    "signals": cmd_signals,
    "evaluate": cmd_evaluate,
    "backtest": cmd_backtest,
    "daily": cmd_daily,
}


def _symbols(text: str) -> list[str]:
    """Parse a comma-separated list of symbols.

    Args:
        text: E.g. ``vcb,fpt``.

    Returns:
        Upper-case symbols.
    """
    return [item.strip().upper() for item in text.split(",") if item.strip()]


def _symbols_lower(text: str) -> list[str]:
    """Parse a comma-separated list of names.

    Args:
        text: E.g. ``logistic,gbdt``.

    Returns:
        Lower-case names.
    """
    return [item.strip().lower() for item in text.split(",") if item.strip()]


def _ints(text: str) -> list[int]:
    """Parse a comma-separated list of integers.

    Args:
        text: E.g. ``1,5``.

    Returns:
        The integers.
    """
    return [int(item) for item in text.split(",") if item.strip()]


if __name__ == "__main__":
    sys.exit(main())
