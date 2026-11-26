# Changelog

All notable changes to this project are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Run the daily job on a Mac with launchd, since Arena refuses GitHub's runners ([#3](https://github.com/nguyenbaanh7779/market-radar/pull/3), [`cef688c`](https://github.com/nguyenbaanh7779/market-radar/pull/3/commits/cef688c3392319eca7ad5ecd5bbc0de9d4ac2bda))
- Add progress reports for the supervisor in `docs/report/` (Vietnamese briefs, one per date), starting with 19/11/2026 ([#5](https://github.com/nguyenbaanh7779/market-radar/pull/5), [`a6998ba`](https://github.com/nguyenbaanh7779/market-radar/pull/5/commits/a6998ba471dc61542f87492cd9e369531a30290a))
- Add the data-understanding notebook `01_data_understanding` with figures in `docs/figures/` ([#6](https://github.com/nguyenbaanh7779/market-radar/pull/6), [`7552050`](https://github.com/nguyenbaanh7779/market-radar/pull/6/commits/7552050ae4f6db061c604e289b78fd01ed7a5220))
- Report highs and lows beyond the ceiling or floor of the day in `market-radar check` ([#6](https://github.com/nguyenbaanh7779/market-radar/pull/6), [`531635c`](https://github.com/nguyenbaanh7779/market-radar/pull/6/commits/531635cde28068c2a954e7ceab4be4105b32919e))
- Add the 26/11/2026 progress report on data understanding ([#6](https://github.com/nguyenbaanh7779/market-radar/pull/6), [`18dd7c3`](https://github.com/nguyenbaanh7779/market-radar/pull/6/commits/18dd7c3c5ffccef8d4636020f2a086d806107c11))

### Changed

- Write the newsletter in plain language: a summary, words first with the real numbers in brackets, confidence words and reasons per stock ([#4](https://github.com/nguyenbaanh7779/market-radar/pull/4), [`2c71314`](https://github.com/nguyenbaanh7779/market-radar/pull/4/commits/2c71314173110406d7b86c03da184f98e489e1e7))
- Apply price limits by the exchange of the day (`exchange_history`, 14 transfers) and void labels across copied bars ([#6](https://github.com/nguyenbaanh7779/market-radar/pull/6), [`2f5a7d5`](https://github.com/nguyenbaanh7779/market-radar/pull/6/commits/2f5a7d5927989cebf524a2aced0ac3ad65319a36), [`531635c`](https://github.com/nguyenbaanh7779/market-radar/pull/6/commits/531635cde28068c2a954e7ceab4be4105b32919e))
- Record the data decisions (θ stays 0.2%, sample stays 2023), the new baseline and the SSI data plan ([#6](https://github.com/nguyenbaanh7779/market-radar/pull/6), [`26c42d6`](https://github.com/nguyenbaanh7779/market-radar/pull/6/commits/26c42d6dd4b52e87cccc516efec9a9a6f2bdd12e), [`baa0015`](https://github.com/nguyenbaanh7779/market-radar/pull/6/commits/baa0015dac21ad3fedc936940a8038d6d36c0e78))

### Fixed

- Stop retrying when the data source refuses access (HTTP 401/403) and exit with code 4 ([#3](https://github.com/nguyenbaanh7779/market-radar/pull/3), [`94afc4a`](https://github.com/nguyenbaanh7779/market-radar/pull/3/commits/94afc4a906e4dae10a662bded97c0608ef0f7d6c))
- Correct the VN30 list from HOSE review results: BVH out, VPL in ([#6](https://github.com/nguyenbaanh7779/market-radar/pull/6), [`7e47177`](https://github.com/nguyenbaanh7779/market-radar/pull/6/commits/7e4717704ab1647dee1d016af9578b1b31b8cf7b))

## [0.1.0] - 2026-11-18

Walking skeleton: the three modules run end to end on real data, with CI and the daily job ([#1](https://github.com/nguyenbaanh7779/market-radar/pull/1))

### Added

- Add the package skeleton: `market-radar` CLI, settings and universe in `config/`, trading calendar ([`1110fbf`](https://github.com/nguyenbaanh7779/market-radar/pull/1/commits/1110fbf9dfa80af0dc962c2d12bb927d6b407dbe), [`3604be8`](https://github.com/nguyenbaanh7779/market-radar/pull/1/commits/3604be8590dc866e9b365559c4f29d5054e9d88a))
- Add the data layer: Arena bars (vnstock v6 optional), Parquet store, quality checks ([`61a0a59`](https://github.com/nguyenbaanh7779/market-radar/pull/1/commits/61a0a59e11f8501d48142be5e3920e8eceb1b625))
- Add Module 1 signals: market state, sector rotation, ticker flags, portfolio status ([`37f3e66`](https://github.com/nguyenbaanh7779/market-radar/pull/1/commits/37f3e669c01f6315826ecb1e449e562fb3f612f8))
- Add Module 2 forecaster: UP/DOWN/SIDEWAY labels, 4 models, purged walk-forward and DM test ([`92ae5c8`](https://github.com/nguyenbaanh7779/market-radar/pull/1/commits/92ae5c84aba906e3da749eb752fab10da80fa35f), [`9544886`](https://github.com/nguyenbaanh7779/market-radar/pull/1/commits/9544886f6151489c918804938a398613a4e2f0b2))
- Add Module 3 paper trading: lots, T+2, fees and tax, weekly rebalance; backtest vs VN30 ([`145bc90`](https://github.com/nguyenbaanh7779/market-radar/pull/1/commits/145bc907c2de5779ec8bb3ee690ca8216fef68d9), [`b88219e`](https://github.com/nguyenbaanh7779/market-radar/pull/1/commits/b88219ef9bf846f51823738a9d375d0ecb67245d))
- Add the daily pipeline: forward-test logs, paper account, Vietnamese Telegram newsletter ([`0fc51e4`](https://github.com/nguyenbaanh7779/market-radar/pull/1/commits/0fc51e43ac14d535a07f4e3b9674eb22fc6d229d), [`5ed321d`](https://github.com/nguyenbaanh7779/market-radar/pull/1/commits/5ed321d5506426b7980b15800d01c6393fce4da2))
- Add GitHub Actions: CI and the 05:30 ICT daily run committing state to the `data` branch ([`44465b9`](https://github.com/nguyenbaanh7779/market-radar/pull/1/commits/44465b9c7ce124f1545142fdb3f64fa13788a104))
- Add docs: research design, architecture and data dictionary, setup guide, 13-week TODO ([`a309488`](https://github.com/nguyenbaanh7779/market-radar/pull/1/commits/a309488aa42444892569ec04c36b192f25ef9a5f), [`6a96864`](https://github.com/nguyenbaanh7779/market-radar/pull/1/commits/6a9686498a8f984d1b72d044b11c053fde6b0137), [`020affe`](https://github.com/nguyenbaanh7779/market-radar/pull/1/commits/020affe4aba42802dda6797a2dad231febe56fc2), [`a626fee`](https://github.com/nguyenbaanh7779/market-radar/pull/1/commits/a626feee9554ba42a4080fbf033ec9fc2aae7ee3), [`1c28ccf`](https://github.com/nguyenbaanh7779/market-radar/pull/1/commits/1c28ccf0e3eca73e48ba60221f6db8151aa15678), [`02c0702`](https://github.com/nguyenbaanh7779/market-radar/pull/1/commits/02c0702f8f19422334bf6a2278239f62176af2ad))

[Unreleased]: https://github.com/nguyenbaanh7779/market-radar/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/nguyenbaanh7779/market-radar/releases/tag/v0.1.0
