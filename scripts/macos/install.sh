#!/bin/bash
# Install (or update) the daily market-radar run on this Mac.
#
#   scripts/macos/install.sh            # from the development checkout
#
# 1. clones the repository to ~/market-radar-runner (or updates it) on main;
# 2. creates its .venv with uv and installs the pinned dependencies;
# 3. copies .env (Telegram) and config/portfolio.yaml if they exist here;
# 4. installs a launchd agent running scripts/macos/run_daily.sh at 05:30,
#    Monday to Friday (local time), and loads it.
#
# Run it again after changing .env or the portfolio. Remove the schedule
# with scripts/macos/uninstall.sh.

set -euo pipefail

LABEL="local.market-radar.daily"
SRC_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
RUNNER_DIR="${MARKET_RADAR_RUNNER:-$HOME/market-radar-runner}"
LOG_DIR="$HOME/Library/Logs/market-radar"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
UV="${UV:-$HOME/.local/bin/uv}"

[ -x "$UV" ] || { echo "uv not found at $UV (see docs/guide/README.md)"; exit 1; }

echo "Runner: $RUNNER_DIR"
if [ ! -d "$RUNNER_DIR/.git" ]; then
    git clone -q "$(git -C "$SRC_DIR" remote get-url origin)" "$RUNNER_DIR"
fi
git -C "$RUNNER_DIR" fetch -q origin main
git -C "$RUNNER_DIR" checkout -q main
git -C "$RUNNER_DIR" merge -q --ff-only origin/main

if [ ! -x "$RUNNER_DIR/.venv/bin/python" ]; then
    "$UV" venv -q --python 3.12 "$RUNNER_DIR/.venv"
fi
"$UV" pip install -q --python "$RUNNER_DIR/.venv/bin/python" \
    -r "$RUNNER_DIR/requirements.txt"
"$UV" pip install -q --python "$RUNNER_DIR/.venv/bin/python" \
    -e "$RUNNER_DIR" --no-deps
cat "$RUNNER_DIR/requirements.txt" "$RUNNER_DIR/pyproject.toml" |
    shasum | cut -d' ' -f1 >"$RUNNER_DIR/.venv/.deps-hash"
if ! "$RUNNER_DIR/.venv/bin/python" -c "import lightgbm" 2>/dev/null; then
    echo "Warning: LightGBM cannot load (libomp); gbdt will fall back to"
    echo "HistGB. See 'LightGBM on macOS without Homebrew' in docs/guide."
fi

for file in .env config/portfolio.yaml; do
    if [ -f "$SRC_DIR/$file" ]; then
        install -m 600 "$SRC_DIR/$file" "$RUNNER_DIR/$file"
        echo "Copied $file"
    fi
done
[ -f "$RUNNER_DIR/.env" ] || echo "Warning: no .env, the newsletter will not be sent."

mkdir -p "$LOG_DIR" "$(dirname "$PLIST")"
{
    cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/caffeinate</string>
        <string>-i</string>
        <string>/bin/bash</string>
        <string>$RUNNER_DIR/scripts/macos/run_daily.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <array>
EOF
    for weekday in 1 2 3 4 5; do
        cat <<EOF
        <dict>
            <key>Weekday</key><integer>$weekday</integer>
            <key>Hour</key><integer>5</integer>
            <key>Minute</key><integer>30</integer>
        </dict>
EOF
    done
    cat <<EOF
    </array>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/launchd.log</string>
</dict>
</plist>
EOF
} >"$PLIST"
plutil -lint -s "$PLIST"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Installed $PLIST (05:30, Monday to Friday)."
echo "Run once now:  launchctl kickstart gui/$(id -u)/$LABEL"
echo "Logs:          $LOG_DIR"
