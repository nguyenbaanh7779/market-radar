#!/bin/bash
# One daily market-radar run on macOS, started by launchd (see
# scripts/macos/install.sh and docs/guide/README.md).
#
# Runs from the runner clone (default ~/market-radar-runner, always on main):
# updates the code, runs `market-radar daily` (retrying while the bars are
# not published), commits the forward-test state to the `data` branch and
# pushes it. On failure it sends a short Telegram message.
#
# The body is a function, so bash reads the whole file before running it:
# the `git merge` below may update this very script.

set -uo pipefail

main() {
    local runner_dir="${MARKET_RADAR_RUNNER:-$HOME/market-radar-runner}"
    local log_dir="$HOME/Library/Logs/market-radar"
    mkdir -p "$log_dir"
    LOG="$log_dir/daily-$(date +%F).log"
    exec >>"$LOG" 2>&1
    echo "=== $(date '+%F %T %Z') start"

    export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    cd "$runner_dir" || fail "runner folder $runner_dir not found"
    load_env

    update_code || fail "could not update the code from origin/main"
    install_deps || fail "could not install the Python dependencies"
    prepare_state || fail "could not prepare the state worktree"

    local status=0 attempt
    for attempt in 1 2 3 4 5 6; do
        status=0
        .venv/bin/market-radar daily --state-dir state --send || status=$?
        [ "$status" -ne 3 ] && break
        echo "Bars not published yet (attempt $attempt); retrying in 15 minutes"
        sleep 900
    done
    [ "$status" -eq 0 ] || fail "market-radar daily exited with code $status"

    publish_state || fail "could not push the state to the data branch"
    echo "=== $(date '+%F %T %Z') done"
}

load_env() {
    # Telegram credentials and optional settings, never committed.
    if [ -f .env ]; then
        set -a
        # shellcheck disable=SC1091
        . ./.env
        set +a
    fi
}

update_code() {
    git fetch -q origin main &&
        git checkout -q main &&
        git merge -q --ff-only origin/main
}

install_deps() {
    # Reinstall only when the pinned requirements or the package change.
    local stamp=".venv/.deps-hash" current
    current="$(cat requirements.txt pyproject.toml | shasum | cut -d' ' -f1)"
    if [ -f "$stamp" ] && [ "$(cat "$stamp")" = "$current" ]; then
        return 0
    fi
    echo "Installing dependencies"
    uv pip install -q --python .venv/bin/python -r requirements.txt &&
        uv pip install -q --python .venv/bin/python -e . --no-deps &&
        echo "$current" >"$stamp"
}

prepare_state() {
    # state/ is a worktree of the `data` branch (created on the first run).
    local remote_has_data=0
    git ls-remote --exit-code --heads origin data >/dev/null && remote_has_data=1
    if [ ! -d state ]; then
        if [ "$remote_has_data" -eq 1 ]; then
            git fetch -q origin data && git worktree add -q -B data state origin/data
        else
            git worktree add -q --orphan -b data state
        fi
        return
    fi
    if [ "$remote_has_data" -eq 1 ]; then
        git -C state fetch -q origin data && git -C state merge -q --ff-only origin/data
    fi
}

publish_state() {
    git -C state add -A
    if ! git -C state diff --cached --quiet; then
        git -C state commit -q -m "state: forward run $(date -u +%Y-%m-%dT%H:%MZ)"
    fi
    # Also pushes commits left behind by an earlier failed push.
    if git -C state rev-parse -q --verify HEAD >/dev/null; then
        git -C state push -q origin data
    fi
}

notify() {
    [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ] || return 0
    curl -s -m 30 -o /dev/null \
        "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
        --data-urlencode "text=$1" || true
}

fail() {
    echo "=== $(date '+%F %T %Z') failed: $1"
    notify "market-radar: lần chạy $(date +%F) lỗi — $1.
Log: $LOG
$(tail -n 12 "$LOG" | cut -c1-200)"
    exit 1
}

main "$@"
