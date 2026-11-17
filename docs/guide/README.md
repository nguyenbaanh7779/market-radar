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

### Personal portfolio

Copy `config/portfolio.example.yaml` to `config/portfolio.yaml`
(gitignored) and list your holdings; prices in thousand VND. The
newsletter then shows your portfolio, but the copy saved under
`state/reports/` never does. Another path can be given with
`MARKET_RADAR_PORTFOLIO=/path/to/file.yaml`.

## 3. Daily runs on GitHub Actions

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
