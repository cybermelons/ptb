#!/bin/bash
# Hook: PostToolUse on Bash
# Checks if state files are getting stale (no writes in last 5 commands).
# Only fires when we're in a machine directory with state files.
set -e

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command')
CWD=$(echo "$INPUT" | jq -r '.cwd')

# Don't count housekeeping
case "$COMMAND" in
  git\ *|ls\ *|ls|cat\ *|pwd|cd\ *|mkdir\ *|chmod\ *)
    exit 0
    ;;
esac

# Only track when working in a machine directory
MACHINE_DIR=$(echo "$CWD" | grep -oP 'machines/[^/]+' || echo "")
if [ -z "$MACHINE_DIR" ]; then
  exit 0
fi

STATEDIR="$CLAUDE_PROJECT_DIR/$MACHINE_DIR/state"

# No state dir yet = too early to nag
if [ ! -d "$STATEDIR" ]; then
  exit 0
fi

TRACKFILE="/tmp/.claude_state_writes"

# Record current mod time of surface.jsonl
SURFACE="$STATEDIR/surface.jsonl"
if [ ! -f "$SURFACE" ]; then
  exit 0
fi

CURRENT_MOD=$(stat -c %Y "$SURFACE" 2>/dev/null || echo 0)

# Read previous mod time and command count since last change
PREV_MOD=0
SINCE_CHANGE=0
if [ -f "$TRACKFILE" ]; then
  PREV_MOD=$(head -1 "$TRACKFILE" 2>/dev/null || echo 0)
  SINCE_CHANGE=$(tail -1 "$TRACKFILE" 2>/dev/null || echo 0)
fi

if [ "$CURRENT_MOD" != "$PREV_MOD" ]; then
  # State was updated — reset counter
  echo "$CURRENT_MOD" > "$TRACKFILE"
  echo "0" >> "$TRACKFILE"
  exit 0
fi

SINCE_CHANGE=$((SINCE_CHANGE + 1))
echo "$PREV_MOD" > "$TRACKFILE"
echo "$SINCE_CHANGE" >> "$TRACKFILE"

if [ "$SINCE_CHANGE" -ge 5 ]; then
  # Reset so we don't nag every command
  echo "$PREV_MOD" > "$TRACKFILE"
  echo "0" >> "$TRACKFILE"
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PostToolUse",
      additionalContext: "STATE STALENESS: 5 commands without updating surface.jsonl. Are you losing findings in conversation? Log discoveries to state files NOW if you have any."
    }
  }'
fi

exit 0
