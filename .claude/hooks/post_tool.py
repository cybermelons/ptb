#!/usr/bin/env python3
"""PostToolUse hook on Bash: error context injection + state staleness.

1. Error context: when a command fails, nudge the agent to READ the error as data
2. State staleness: after 5 commands without updating state files, nudge
"""
import json, sys, os, re

SKIP = ('git ', 'ls', 'cat ', 'pwd', 'cd ', 'mkdir ', 'chmod ', 'echo ')
STATE_TRACK_FILE = '/tmp/.claude_state_writes'


def error_context(tool_response):
    """If command failed, inject context about reading errors as data."""
    # tool_response contains stdout/stderr from the command
    resp_str = str(tool_response)

    # Check for common error indicators
    error_indicators = [
        'error', 'Error', 'ERROR',
        'traceback', 'Traceback',
        'exception', 'Exception',
        'denied', 'refused', 'timeout',
        'INVALID', 'FAIL', 'fatal',
    ]

    has_error = any(indicator in resp_str for indicator in error_indicators)
    if not has_error:
        return None

    return (
        "ERROR SIGNAL: This output contains error/diagnostic information. "
        "Read the error MESSAGE CONTENT as data about the target's internals — "
        "exception types, stack traces, and error strings reveal the implementation. "
        "Don't just record 'failed' — extract what the error TELLS you."
    )


def state_staleness(command, cwd):
    """After 5 non-trivial commands without updating state files, nudge."""
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
            "STATE STALENESS: 5 commands without updating state files. "
            "Are you losing findings in conversation? "
            "Log discoveries to state files NOW if you have any."
        )
    return None


def main():
    data = json.load(sys.stdin)
    command = data.get('tool_input', {}).get('command', '')
    cwd = data.get('cwd', '')
    tool_response = data.get('tool_response', '')

    messages = []

    err = error_context(tool_response)
    if err:
        messages.append(err)

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
