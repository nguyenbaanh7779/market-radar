#!/bin/bash
# Remove the daily market-radar schedule from this Mac. The runner clone
# (~/market-radar-runner) and the logs are kept; delete them by hand if
# they are no longer needed.

set -euo pipefail

LABEL="local.market-radar.daily"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$PLIST"
echo "Removed the $LABEL schedule."
