#!/usr/bin/env sh
# PostToolUse hook for Claude Code. Triggers on Edit/Write under docs/sdlc/.
# Reads the JSON payload Claude provides on stdin, extracts the file path, and runs propagation.

set -e
PAYLOAD=$(cat)
FILE=$(printf '%s' "$PAYLOAD" | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1)

if [ -z "$FILE" ]; then
  exit 0
fi
case "$FILE" in
  *docs/sdlc/*.md) ;;
  *) exit 0 ;;
esac

node "$(dirname "$0")/../../scripts/sdlc-propagate.js" "$FILE" || true
node "$(dirname "$0")/../../scripts/sdlc-graph.js" >/dev/null || true
