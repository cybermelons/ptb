#!/bin/bash
# Hook: PreToolUse on Bash
# Logs every command to ./logs/actions.jsonl before execution.
# This is mechanical — the agent doesn't have to remember to do it.
set -e

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command')
CWD=$(echo "$INPUT" | jq -r '.cwd')

# Skip logging for git commands, ls, and other non-pentest housekeeping
case "$COMMAND" in
  git\ *|ls\ *|ls|cat\ ./state/*|cat\ ./logs/*|pwd|cd\ *)
    exit 0
    ;;
esac

# Determine phase from CWD — if we're in a machine dir, use it
MACHINE_DIR=$(echo "$CWD" | grep -oP 'machines/[^/]+' || echo "")

# Ensure logs directory exists
LOGDIR="$CLAUDE_PROJECT_DIR/logs"
if [ -n "$MACHINE_DIR" ]; then
  LOGDIR="$CLAUDE_PROJECT_DIR/$MACHINE_DIR/logs"
fi
mkdir -p "$LOGDIR" 2>/dev/null || true

# Append action log entry
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "$INPUT" | jq -c --arg ts "$TS" --arg cmd "$COMMAND" '{
  action: $cmd,
  ts: $ts
}' >> "$LOGDIR/actions.jsonl" 2>/dev/null || true

exit 0
