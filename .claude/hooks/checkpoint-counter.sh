#!/bin/bash
# Hook: PostToolUse on Bash
# Counts Bash calls since last checkpoint. After 10, reminds agent to assess.
set -e

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command')

# Don't count housekeeping commands
case "$COMMAND" in
  git\ *|ls\ *|ls|cat\ *|pwd|cd\ *|mkdir\ *|chmod\ *)
    exit 0
    ;;
esac

COUNTERFILE="/tmp/.claude_action_counter"

# Read current count
COUNT=0
if [ -f "$COUNTERFILE" ]; then
  COUNT=$(cat "$COUNTERFILE" 2>/dev/null || echo 0)
fi

COUNT=$((COUNT + 1))
echo "$COUNT" > "$COUNTERFILE"

if [ "$COUNT" -ge 10 ]; then
  # Reset counter
  echo "0" > "$COUNTERFILE"
  # Send reminder back to agent
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PostToolUse",
      additionalContext: "CHECKPOINT REMINDER: 10 actions since last checkpoint. Classify recent failures (soft/hard). Update state files if you have unlogged discoveries. Write checkpoint to ./logs/checkpoint.md if changing direction."
    }
  }'
fi

exit 0
