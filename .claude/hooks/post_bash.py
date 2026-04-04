#!/usr/bin/env python3
"""PostToolUse hook on Bash: checkpoint counter + state staleness check."""
import json, sys, os, re

SKIP = ('git ', 'ls', 'cat ', 'pwd', 'cd ', 'mkdir ', 'chmod ', 'echo ')
COUNTER_FILE = '/tmp/.claude_action_counter'
STATE_TRACK_FILE = '/tmp/.claude_state_writes'


def checkpoint_counter(command):
    """After 10 non-housekeeping commands, remind agent to assess."""
    if any(command.startswith(p) for p in SKIP):
        return None

    count = 0
    try:
        with open(COUNTER_FILE) as f:
            count = int(f.read().strip())
    except (OSError, ValueError):
        pass

    count += 1

    with open(COUNTER_FILE, 'w') as f:
        f.write(str(count))

    if count >= 10:
        with open(COUNTER_FILE, 'w') as f:
            f.write('0')
        return (
            "CHECKPOINT REMINDER: 10 actions since last checkpoint. "
            "Classify recent failures (soft/hard). "
            "Update state files if you have unlogged discoveries. "
            "Write checkpoint to ./logs/checkpoint.md if changing direction."
        )
    return None


def state_staleness(command, cwd):
    """After 5 commands without updating surface.jsonl, nudge agent."""
    if any(command.startswith(p) for p in SKIP):
        return None

    project_dir = os.environ.get('CLAUDE_PROJECT_DIR', '/htb')
    m = re.search(r'machines/[^/]+', cwd)
    if not m:
        return None

    surface = os.path.join(project_dir, m.group(), 'state', 'surface.jsonl')
    if not os.path.exists(surface):
        return None

    current_mod = int(os.path.getmtime(surface))

    prev_mod = 0
    since_change = 0
    try:
        with open(STATE_TRACK_FILE) as f:
            lines = f.read().strip().split('\n')
            prev_mod = int(lines[0])
            since_change = int(lines[1])
    except (OSError, ValueError, IndexError):
        pass

    if current_mod != prev_mod:
        with open(STATE_TRACK_FILE, 'w') as f:
            f.write(f'{current_mod}\n0\n')
        return None

    since_change += 1
    with open(STATE_TRACK_FILE, 'w') as f:
        f.write(f'{prev_mod}\n{since_change}\n')

    if since_change >= 5:
        with open(STATE_TRACK_FILE, 'w') as f:
            f.write(f'{prev_mod}\n0\n')
        return (
            "STATE STALENESS: 5 commands without updating surface.jsonl. "
            "Are you losing findings in conversation? "
            "Log discoveries to state files NOW if you have any."
        )
    return None


def main():
    data = json.load(sys.stdin)
    command = data.get('tool_input', {}).get('command', '')
    cwd = data.get('cwd', '')

    messages = []
    cp = checkpoint_counter(command)
    if cp:
        messages.append(cp)
    st = state_staleness(command, cwd)
    if st:
        messages.append(st)

    if messages:
        output = {
            'hookSpecificOutput': {
                'hookEventName': 'PostToolUse',
                'additionalContext': ' | '.join(messages),
            }
        }
        json.dump(output, sys.stdout)

    sys.exit(0)

if __name__ == '__main__':
    main()
