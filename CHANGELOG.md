# CHANGELOG

## Unreleased

### Features

- Add the package skeleton: `market-radar` CLI, settings and universe in `config/`, trading calendar ([`1110fbf`](https://github.com/nguyenbaanh7779/market-radar/commit/1110fbf9dfa80af0dc962c2d12bb927d6b407dbe), [`3604be8`](https://github.com/nguyenbaanh7779/market-radar/commit/3604be8590dc866e9b365559c4f29d5054e9d88a))
- Add the data layer: Arena bars (vnstock v6 optional), Parquet store, quality checks ([`61a0a59`](https://github.com/nguyenbaanh7779/market-radar/commit/61a0a59e11f8501d48142be5e3920e8eceb1b625))
- Add Module 1 signals: market state, sector rotation, ticker flags, portfolio status ([`37f3e66`](https://github.com/nguyenbaanh7779/market-radar/commit/37f3e669c01f6315826ecb1e449e562fb3f612f8))
- Add Module 2 forecaster: UP/DOWN/SIDEWAY labels, 4 models, purged walk-forward and DM test ([`92ae5c8`](https://github.com/nguyenbaanh7779/market-radar/commit/92ae5c84aba906e3da749eb752fab10da80fa35f), [`9544886`](https://github.com/nguyenbaanh7779/market-radar/commit/9544886f6151489c918804938a398613a4e2f0b2))
- Add Module 3 paper trading: lots, T+2, fees and tax, weekly rebalance; backtest vs VN30 ([`145bc90`](https://github.com/nguyenbaanh7779/market-radar/commit/145bc907c2de5779ec8bb3ee690ca8216fef68d9), [`b88219e`](https://github.com/nguyenbaanh7779/market-radar/commit/b88219ef9bf846f51823738a9d375d0ecb67245d))
- Add the daily pipeline: forward-test logs, paper account, Vietnamese Telegram newsletter ([`0fc51e4`](https://github.com/nguyenbaanh7779/market-radar/commit/0fc51e43ac14d535a07f4e3b9674eb22fc6d229d), [`5ed321d`](https://github.com/nguyenbaanh7779/market-radar/commit/5ed321d5506426b7980b15800d01c6393fce4da2))
- Add GitHub Actions: CI and the 05:30 ICT daily run committing state to the `data` branch ([`44465b9`](https://github.com/nguyenbaanh7779/market-radar/commit/44465b9c7ce124f1545142fdb3f64fa13788a104))
- Add docs: research design, architecture and data dictionary, setup guide, 13-week TODO ([`a309488`](https://github.com/nguyenbaanh7779/market-radar/commit/a309488aa42444892569ec04c36b192f25ef9a5f), [`6a96864`](https://github.com/nguyenbaanh7779/market-radar/commit/6a9686498a8f984d1b72d044b11c053fde6b0137), [`020affe`](https://github.com/nguyenbaanh7779/market-radar/commit/020affe4aba42802dda6797a2dad231febe56fc2), [`a626fee`](https://github.com/nguyenbaanh7779/market-radar/commit/a626feee9554ba42a4080fbf033ec9fc2aae7ee3), [`1c28ccf`](https://github.com/nguyenbaanh7779/market-radar/commit/1c28ccf0e3eca73e48ba60221f6db8151aa15678))
