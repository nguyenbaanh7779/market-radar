# Changelog

All notable changes to this project are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-11-18

Walking skeleton: the three modules run end to end on real data, with CI and the daily job.

### Added

- Add the package skeleton: `market-radar` CLI, settings and universe in `config/`, trading calendar ([#1](https://github.com/nguyenbaanh7779/market-radar/pull/1))
- Add the data layer: Arena bars (vnstock v6 optional), Parquet store, quality checks ([#1](https://github.com/nguyenbaanh7779/market-radar/pull/1))
- Add Module 1 signals: market state, sector rotation, ticker flags, portfolio status ([#1](https://github.com/nguyenbaanh7779/market-radar/pull/1))
- Add Module 2 forecaster: UP/DOWN/SIDEWAY labels, 4 models, purged walk-forward and DM test ([#1](https://github.com/nguyenbaanh7779/market-radar/pull/1))
- Add Module 3 paper trading: lots, T+2, fees and tax, weekly rebalance; backtest vs VN30 ([#1](https://github.com/nguyenbaanh7779/market-radar/pull/1))
- Add the daily pipeline: forward-test logs, paper account, Vietnamese Telegram newsletter ([#1](https://github.com/nguyenbaanh7779/market-radar/pull/1))
- Add GitHub Actions: CI and the 05:30 ICT daily run committing state to the `data` branch ([#1](https://github.com/nguyenbaanh7779/market-radar/pull/1))
- Add docs: research design, architecture and data dictionary, setup guide, 13-week TODO ([#1](https://github.com/nguyenbaanh7779/market-radar/pull/1))

[Unreleased]: https://github.com/nguyenbaanh7779/market-radar/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/nguyenbaanh7779/market-radar/releases/tag/v0.1.0
