# Setup Guide

## 1. Python environment

The project needs Python ≥ 3.12 in a virtual environment at `.venv/`.
On macOS, keep Apple's `/usr/bin/python3` (3.9, part of the Command Line
Tools that also provide `git`); install 3.12 next to it with
[uv](https://docs.astral.sh/uv/):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # installs uv to ~/.local/bin
exec zsh                                          # reload PATH
uv python install 3.12 --default                  # python3 -> 3.12 in new shells
```

Then, from the repository root:

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv pip install -e . --no-deps
pytest -q && ruff check .
```

`requirements.txt` pins every package; `pyproject.toml` lists the direct
dependencies. After changing them, regenerate the pins with
`uv pip freeze --exclude-editable > requirements.txt`.

In VS Code, pick `.venv/bin/python` with *Python: Select Interpreter*.

### LightGBM on macOS without Homebrew (libomp)

LightGBM's macOS wheel loads `libomp.dylib`, normally installed with
`brew install libomp`. Without Homebrew, `import lightgbm` fails and the
`gbdt` model falls back to scikit-learn's HistGB (logged as
`gbdt-histgb-…`, without explanations). scikit-learn ships its own copy of
libomp; link it into the `lib/` folder of the uv Python, which LightGBM
searches (one OpenMP runtime, no sudo):

```bash
ln -sf "$PWD/.venv/lib/python3.12/site-packages/sklearn/.dylibs/libomp.dylib" \
  "$(python3 -c 'import sys; print(sys.base_prefix)')/lib/libomp.dylib"
python -c "import lightgbm"   # no error = fixed
```

The link points into `.venv`; run the command again after recreating it.
Linux (and the GitHub runners) need nothing extra.

## 2. Running locally

```bash
market-radar update      # download bars (first run ~2 minutes)
market-radar check       # data-quality report
market-radar signals     # Module 1 on the latest session
market-radar evaluate    # walk-forward evaluation (~5 minutes)
market-radar backtest    # paper trading on out-of-sample forecasts
market-radar daily --state-dir /tmp/mr-state   # one full run, prints the newsletter
```

`daily` exits with code 3 when the session it expects has not been
published yet (Arena publishes overnight). Results go to `data/` and
forward-test state to `state/` (both gitignored).

### Telegram and other secrets

```bash
cp .env.example .env          # gitignored; fill in the values
set -a; source .env; set +a   # once per terminal session
market-radar daily --state-dir /tmp/mr-tg --send
```

### Personal portfolio

Copy `config/portfolio.example.yaml` to `config/portfolio.yaml`
(gitignored) and list your holdings; prices in thousand VND. The
newsletter then shows your portfolio, but the copy saved under
`state/reports/` never does. Another path can be given with
`MARKET_RADAR_PORTFOLIO=/path/to/file.yaml`.

## 3. Daily runs on your Mac

Arena refuses requests from cloud servers such as GitHub's runners (HTTP
403), so the daily run happens on a Mac in Vietnam, scheduled by launchd.
It uses a separate clone, `~/market-radar-runner`, always on `main`, so
work in progress in the development checkout never changes the forward
test (and launchd needs no access to `~/Documents`).

```bash
scripts/macos/install.sh       # clone/update the runner, .venv, copy .env, schedule
launchctl kickstart gui/$(id -u)/local.market-radar.daily   # run once now
scripts/macos/uninstall.sh     # remove the schedule (keeps the runner)
```

- **Schedule:** 05:30, Monday to Friday, local time. A run missed while the
  Mac sleeps starts as soon as it wakes; nothing runs while it is shut down.
  To wake it a few minutes before (works best on power):
  `sudo pmset repeat wakeorpoweron MTWRF 05:25:00`.
- **Each run** (`scripts/macos/run_daily.sh`): fast-forwards `main`,
  reinstalls dependencies when `requirements.txt` or `pyproject.toml`
  changed, runs `market-radar daily --send` (retrying every 15 minutes, up
  to 6 times, while the bars are not published), then commits `state/` and
  pushes it to the `data` branch over SSH (a key without a passphrase, or
  one the launchd session can use).
- **On failure** it sends a short Telegram message with the last log lines.
  Exit code 4 means the data source refused the machine.
- **Logs:** `~/Library/Logs/market-radar/daily-<date>.log`.
- Re-run `install.sh` after changing `.env` or `config/portfolio.yaml`; the
  runner keeps its own copies.

## 3b. Daily runs on GitHub Actions (disabled)

The `daily` workflow is kept but **disabled** in the Actions tab, because
Arena answers 403 to GitHub's runners. Enable it again if Arena allows
cloud access (TODO.md); its setup is below.

`.github/workflows/daily.yml` runs at 05:30 ICT on weekdays (and on
demand) and commits the forward-test state to the `data` branch, which it
creates on the first run.

1. Push `main` to GitHub.
2. *Settings → Actions → General → Workflow permissions*: choose **Read
   and write permissions** (the job pushes to `data`).
3. *Settings → Secrets and variables → Actions*, add what you use:

   | Secret | Purpose |
   |---|---|
   | `TELEGRAM_BOT_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather) (`/newbot`) |
   | `TELEGRAM_CHAT_ID` | Your chat id: send the bot a message, then open `https://api.telegram.org/bot<token>/getUpdates` and read `message.chat.id` |
   | `PORTFOLIO_YAML` | The content of your `config/portfolio.yaml` |

4. *Actions → daily → Run workflow* once to check everything works; the
   first run downloads the full history (~2 minutes) and caches it.

To read the forward-test state locally:

```bash
git fetch origin data
git worktree add state origin/data     # read-only copy in state/
```

The schedule is in UTC (`30 22 * * 0-4` = 05:30 ICT Monday–Friday).
Scheduled workflows of a public repository stop after 60 days without
activity in it; any push re-enables them.

## 4. Optional: vnstock v6 (volume and evening runs)

vnstock is no longer on PyPI. Generation 6 installs from its own index
and needs an API key from a securities company (`ssi`, `dnse`, `tcbs` or
`fhsc`); see [vnstocks.com/onboard](https://vnstocks.com/onboard).

```bash
uv pip install --extra-index-url https://vnstocks.com/api/packages \
    "vnstock==6.0.1" "vnstock-oapi==0.1.2"
vnstock keys set ssi          # paste the key here, never into a chat
```

Then set `data.source: vnstock` and `data.vnstock.provider` in
`config/settings.yaml`, and `schedule.publish_lag_days: 0` if the
provider has the day's bars in the evening (move the cron to about
`30 10 * * 1-5` = 17:30 ICT). The adapter in
`src/market_radar/data/sources.py` follows the documented v6 API and has
not been tested against a live key yet. Running it in GitHub Actions
needs the key stored as a secret; check vnstock's documentation for
non-interactive key setup first.

## 5. Maintenance

- **Holidays:** add upcoming exchange holidays to `config/holidays.yaml`
  (Tet 2027 once HOSE announces it). A missing holiday makes the job wait
  and then fail on that day; nothing else breaks.
- **Universe:** update `config/universe.yaml` after the VN30 reviews
  (January and July).
- **Arena API changes:** `tests/test_sources.py` documents the response
  format the code expects.
