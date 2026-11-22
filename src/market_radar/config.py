"""Typed settings and instrument universe loaded from ``config/``."""

from __future__ import annotations

import copy
import dataclasses
import datetime as dt
import hashlib
import json
import os
import types
import typing
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = "config"
ROOT_ENV_VAR = "MARKET_RADAR_ROOT"


@dataclasses.dataclass(frozen=True)
class PathSettings:
    """Folders used by the pipeline, relative to the repository root."""

    data_dir: str = "data"
    state_dir: str = "state"


@dataclasses.dataclass(frozen=True)
class ArenaSettings:
    """Connection settings for the Arena (ckai.vn) public API."""

    base_url: str = "https://ckai.vn/vi/api"
    timeout_s: float = 60.0
    pause_s: float = 0.3
    retries: int = 3


@dataclasses.dataclass(frozen=True)
class VnstockSettings:
    """Settings for the optional vnstock v6 source."""

    provider: str = "ssi"
    pause_s: float = 3.5


@dataclasses.dataclass(frozen=True)
class DataSettings:
    """Where market data comes from and which period is used."""

    source: str = "arena"
    fetch_start: dt.date = dt.date(2019, 1, 1)
    sample_start: dt.date = dt.date(2023, 1, 1)
    overlap_days: int = 15
    arena: ArenaSettings = ArenaSettings()
    vnstock: VnstockSettings = VnstockSettings()


@dataclasses.dataclass(frozen=True)
class ScheduleSettings:
    """When a run happens relative to the data it needs."""

    timezone: str = "Asia/Ho_Chi_Minh"
    publish_lag_days: int = 1


@dataclasses.dataclass(frozen=True)
class LabelSettings:
    """Direction label definition."""

    horizons: tuple[int, ...] = (1, 5)
    sideway_band_pct: float = 0.2


@dataclasses.dataclass(frozen=True)
class FeatureSettings:
    """Feature construction options."""

    min_volume_coverage: float = 0.9


@dataclasses.dataclass(frozen=True)
class WalkForwardSettings:
    """Expanding-window walk-forward validation."""

    min_train_sessions: int = 250
    test_sessions: int = 21
    embargo_sessions: int = 5


@dataclasses.dataclass(frozen=True)
class ModelSettings:
    """Candidate models and their hyperparameters."""

    primary: str = "logistic"
    candidates: tuple[str, ...] = (
        "majority", "momentum", "logistic", "gbdt",
    )
    logistic: dict[str, Any] = dataclasses.field(default_factory=dict)
    gbdt: dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class SignalSettings:
    """Thresholds for the rule-based signals of Module 1."""

    rsi_strong_low: float = 50.0
    rsi_strong_high: float = 70.0
    rsi_overbought: float = 75.0
    volume_spike_ratio: float = 1.5
    rrg_window: int = 50
    rrg_momentum_lag: int = 10
    vol_pctile_window: int = 250
    high_vol_pctile: float = 0.8


@dataclasses.dataclass(frozen=True)
class TradingSettings:
    """Paper-trading rules of Module 3."""

    initial_capital_vnd: float = 100_000_000
    horizon: int = 5
    top_k: int = 5
    rebalance_every_sessions: int = 5
    min_p_up: float = 0.40
    max_weight: float = 0.30
    stop_loss_pct: float = 7.0
    lot_size: int = 100
    settlement_sessions: int = 2
    buy_fee_pct: float = 0.15
    sell_fee_pct: float = 0.15
    sell_tax_pct: float = 0.10
    price_unit_vnd: float = 1000.0
    benchmark: str = "VN30"


@dataclasses.dataclass(frozen=True)
class ReportSettings:
    """Newsletter options."""

    language: str = "vi"
    top_n: int = 5
    outlook_symbols: tuple[str, ...] = ("VNINDEX", "VN30", "BANKS")
    guide_url: str = (
        "https://github.com/nguyenbaanh7779/market-radar/blob/main/docs/"
        "guide/newsletter-vi.md")


@dataclasses.dataclass(frozen=True)
class Listing:
    """An earlier listing of a stock that later changed exchange.

    Attributes:
        exchange: Exchange code of the earlier listing.
        until: Last session traded on that exchange.
        source: Where the transfer date comes from (URL or note).
    """

    exchange: str
    until: dt.date
    source: str = ""


@dataclasses.dataclass(frozen=True)
class Universe:
    """Instruments covered by the agent.

    Attributes:
        as_of: Date the lists were last reviewed.
        indices: Exchange indices (e.g. VNINDEX, VN30).
        baskets: Synthetic equal-weight baskets, mapped to the sector whose
            members they average.
        vn30: VN30 constituents.
        vn30_verified: Whether ``vn30`` was checked against HOSE.
        banks: Listed banks.
        sectors: Sector name to member stocks.
        exchanges: Current exchange of each non-HOSE stock.
        price_limits_pct: Daily price limit per exchange, in percent.
        exchange_history: Earlier listings per stock, oldest first, for
            stocks that changed exchange during the sample.
        first_session_limit_pct: Price limit of the first session on a
            new exchange, in percent.
    """

    as_of: dt.date
    indices: tuple[str, ...]
    baskets: dict[str, str]
    vn30: tuple[str, ...]
    vn30_verified: bool
    banks: tuple[str, ...]
    sectors: dict[str, tuple[str, ...]]
    exchanges: dict[str, str]
    price_limits_pct: dict[str, float]
    exchange_history: dict[str, tuple[Listing, ...]] = dataclasses.field(
        default_factory=dict)
    first_session_limit_pct: float = 20.0

    @property
    def stocks(self) -> tuple[str, ...]:
        """Return every stock in the universe, sorted."""
        members = set(self.vn30) | set(self.banks)
        for tickers in self.sectors.values():
            members |= set(tickers)
        return tuple(sorted(members))

    @property
    def fetch_symbols(self) -> tuple[str, ...]:
        """Return the symbols whose bars are downloaded (no baskets)."""
        return self.indices + self.stocks

    @property
    def instruments(self) -> tuple[str, ...]:
        """Return everything that gets a forecast: indices, baskets, stocks."""
        return self.indices + tuple(self.baskets) + self.stocks

    def is_index_like(self, symbol: str) -> bool:
        """Tell whether a symbol is an index or a synthetic basket.

        Args:
            symbol: Instrument symbol.

        Returns:
            True for indices and baskets, False for stocks.
        """
        return symbol in self.indices or symbol in self.baskets

    def sector_of(self, symbol: str) -> str | None:
        """Return the sector of a stock.

        Args:
            symbol: Stock symbol.

        Returns:
            The first sector listing the stock, or None if it has none.
        """
        for sector, tickers in self.sectors.items():
            if symbol in tickers:
                return sector
        return None

    def exchange_of(self, symbol: str, date: dt.date | None = None) -> str:
        """Return the exchange of a symbol (HOSE unless listed otherwise).

        Args:
            symbol: Instrument symbol.
            date: Session to look up; the current exchange when omitted.

        Returns:
            Exchange code such as ``HOSE``, ``HNX`` or ``UPCOM``.
        """
        if date is not None:
            for listing in self.exchange_history.get(symbol, ()):
                if date <= listing.until:
                    return listing.exchange
        return self.exchanges.get(symbol, "HOSE")

    def price_limit_pct(
        self, symbol: str, date: dt.date | None = None
    ) -> float:
        """Return the daily price limit that applies to a symbol.

        Args:
            symbol: Instrument symbol.
            date: Session to look up; the current limit when omitted.

        Returns:
            Limit in percent of the reference price.
        """
        return self.price_limits_pct[self.exchange_of(symbol, date)]

    def limit_rules(self) -> dict[str, Any]:
        """Return the price-limit rules that decide which labels are void.

        Returns:
            Limits per exchange, the first-session limit, current
            exchanges and the transfer dates, as plain values.
        """
        return {
            "limits": self.price_limits_pct,
            "first_session": self.first_session_limit_pct,
            "exchanges": self.exchanges,
            "history": {
                symbol: [(item.exchange, item.until.isoformat())
                         for item in listings]
                for symbol, listings in self.exchange_history.items()
            },
        }


@dataclasses.dataclass(frozen=True)
class Settings:
    """All settings of a market-radar run.

    Attributes:
        root: Repository root that relative paths are resolved against.
        paths: Data and state folders.
        data: Data source and period.
        schedule: Run timing.
        labels: Label definition.
        features: Feature options.
        walk_forward: Validation scheme.
        models: Candidate models.
        signals: Signal thresholds.
        trading: Paper-trading rules.
        report: Newsletter options.
        universe: Instruments covered.
        holidays: Exchange holidays for projecting future sessions.
    """

    root: Path
    paths: PathSettings
    data: DataSettings
    schedule: ScheduleSettings
    labels: LabelSettings
    features: FeatureSettings
    walk_forward: WalkForwardSettings
    models: ModelSettings
    signals: SignalSettings
    trading: TradingSettings
    report: ReportSettings
    universe: Universe
    holidays: frozenset[dt.date]

    @property
    def data_dir(self) -> Path:
        """Return the absolute data folder."""
        return self.root / self.paths.data_dir

    @property
    def state_dir(self) -> Path:
        """Return the absolute default forward-test state folder."""
        return self.root / self.paths.state_dir

    @property
    def config_dir(self) -> Path:
        """Return the absolute config folder."""
        return self.root / CONFIG_DIR

    def fingerprint(self) -> str:
        """Hash the settings that change model outputs.

        Returns:
            Eight hex characters identifying the label, feature, sample and
            model settings, used in model version strings.
        """
        payload = {
            "labels": dataclasses.asdict(self.labels),
            "features": dataclasses.asdict(self.features),
            "sample_start": self.data.sample_start.isoformat(),
            "models": dataclasses.asdict(self.models),
            "price_limits": self.universe.limit_rules(),
        }
        text = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha1(text.encode()).hexdigest()[:8]


def find_root(start: Path | None = None) -> Path:
    """Locate the repository root, i.e. the folder with ``config/``.

    The ``MARKET_RADAR_ROOT`` environment variable wins; otherwise the
    current folder and its parents are searched, then the source tree.

    Args:
        start: Folder to start searching from (default: current folder).

    Returns:
        Absolute path of the repository root.

    Raises:
        FileNotFoundError: If no ``config/settings.yaml`` can be found.
    """
    env_root = os.environ.get(ROOT_ENV_VAR)
    if env_root:
        return Path(env_root).resolve()
    here = (start or Path.cwd()).resolve()
    candidates = [here, *here.parents, Path(__file__).resolve().parents[2]]
    for folder in candidates:
        if (folder / CONFIG_DIR / "settings.yaml").is_file():
            return folder
    raise FileNotFoundError(
        f"No {CONFIG_DIR}/settings.yaml found from {here}; run inside the "
        f"repository or set {ROOT_ENV_VAR}."
    )


def load_settings(
    root: Path | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> Settings:
    """Load ``settings.yaml``, ``universe.yaml`` and ``holidays.yaml``.

    Args:
        root: Repository root; found automatically when omitted.
        overrides: Nested mapping merged over ``settings.yaml``, e.g.
            ``{"walk_forward": {"test_sessions": 10}}`` (used by tests).

    Returns:
        The validated settings.
    """
    root = Path(root).resolve() if root else find_root()
    config_dir = root / CONFIG_DIR
    raw = _read_yaml(config_dir / "settings.yaml")
    if overrides:
        raw = _deep_merge(raw, overrides)
    sections = {
        field.name: _build(_section_type(field.name), raw.pop(field.name, {}))
        for field in dataclasses.fields(Settings)
        if field.name not in ("root", "universe", "holidays")
    }
    if raw:
        raise KeyError(f"Unknown settings sections: {sorted(raw)}")
    universe = load_universe(config_dir / "universe.yaml")
    holidays = load_holidays(config_dir / "holidays.yaml")
    return Settings(
        root=root, universe=universe, holidays=holidays, **sections
    )


def load_universe(path: Path) -> Universe:
    """Read the instrument universe.

    Args:
        path: Path of ``universe.yaml``.

    Returns:
        The universe with exchanges mapped per symbol.
    """
    raw = _read_yaml(path)
    exchanges = {
        symbol: exchange.upper()
        for exchange, symbols in (raw.get("exchanges") or {}).items()
        for symbol in symbols
    }
    vn30 = raw.get("vn30") or {}
    history = {
        symbol: tuple(sorted(
            (Listing(exchange=str(item["exchange"]).upper(),
                     until=_to_date(item["until"]),
                     source=str(item.get("source", "")))
             for item in listings),
            key=lambda listing: listing.until,
        ))
        for symbol, listings in (raw.get("exchange_history") or {}).items()
    }
    return Universe(
        as_of=_to_date(raw["as_of"]),
        indices=tuple(raw.get("indices") or ()),
        baskets=dict(raw.get("baskets") or {}),
        vn30=tuple(vn30.get("members") or ()),
        vn30_verified=bool(vn30.get("verified", False)),
        banks=tuple(raw.get("banks") or ()),
        sectors={
            name: tuple(members)
            for name, members in (raw.get("sectors") or {}).items()
        },
        exchanges=exchanges,
        price_limits_pct={
            key.upper(): float(value)
            for key, value in raw["price_limits_pct"].items()
        },
        exchange_history=history,
        first_session_limit_pct=float(
            raw.get("first_session_limit_pct", 20.0)),
    )


def load_holidays(path: Path) -> frozenset[dt.date]:
    """Read the exchange holiday list.

    Args:
        path: Path of ``holidays.yaml``; a missing file means no holidays.

    Returns:
        The holiday dates.
    """
    if not path.is_file():
        return frozenset()
    raw = _read_yaml(path)
    return frozenset(_to_date(day) for day in raw.get("holidays") or ())


def _read_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML mapping.

    Args:
        path: File to read.

    Returns:
        The parsed mapping (empty for an empty file).
    """
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _deep_merge(
    base: Mapping[str, Any], extra: Mapping[str, Any]
) -> dict[str, Any]:
    """Merge nested mappings, values from ``extra`` winning.

    Args:
        base: Original mapping.
        extra: Mapping whose values override ``base``.

    Returns:
        A new merged mapping.
    """
    merged = copy.deepcopy(dict(base))
    for key, value in extra.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _section_type(name: str) -> type:
    """Return the dataclass type of a top-level settings section.

    Args:
        name: Field name on :class:`Settings`.

    Returns:
        The dataclass used for that section.
    """
    return typing.get_type_hints(Settings)[name]


def _build(cls: type, data: Mapping[str, Any] | None) -> Any:
    """Build a settings dataclass from a mapping, recursively.

    Args:
        cls: Dataclass type to build.
        data: Values from YAML; missing keys keep their defaults.

    Returns:
        An instance of ``cls``.

    Raises:
        KeyError: If ``data`` has keys that ``cls`` does not define.
    """
    data = dict(data or {})
    hints = typing.get_type_hints(cls)
    names = {field.name for field in dataclasses.fields(cls)}
    unknown = set(data) - names
    if unknown:
        raise KeyError(f"Unknown keys for {cls.__name__}: {sorted(unknown)}")
    values = {
        name: _coerce(hints[name], value) for name, value in data.items()
    }
    return cls(**values)


def _coerce(hint: Any, value: Any) -> Any:
    """Convert a YAML value to the annotated field type.

    Args:
        hint: Resolved type annotation of the field.
        value: Raw YAML value.

    Returns:
        The converted value.
    """
    if value is None:
        return None
    if dataclasses.is_dataclass(hint):
        return _build(hint, value)
    origin = typing.get_origin(hint)
    if origin in (typing.Union, types.UnionType):
        inner = [arg for arg in typing.get_args(hint) if arg is not type(None)]
        return _coerce(inner[0], value)
    if hint is dt.date:
        return _to_date(value)
    if origin is tuple:
        return tuple(value)
    if hint in (int, float, str, bool):
        return hint(value)
    return value


def _to_date(value: Any) -> dt.date:
    """Parse a date given as text or a YAML date.

    Args:
        value: ``YYYY-MM-DD`` text or a date object.

    Returns:
        The date.
    """
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value))
