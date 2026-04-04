#!/usr/bin/env python3
"""PreToolUse hook: logs every Bash command to ./logs/actions.jsonl before execution."""
import json
import sys
import os
from datetime import datetime, timezone

SKIP_PREFIXES = ('git ', 'ls', 'cat ./state/', 'cat ./logs/', 'pwd', 'cd ')

def main():
    data = json.load(sys.stdin)
    command = data.get('tool_input', {}).get('command', '')
    cwd = data.get('cwd', '')

    # Skip housekeeping commands
    if any(command.startswith(p) for p in SKIP_PREFIXES):
        return

    # Determine log directory — use machine dir if we're in one
    project_dir = os.environ.get('CLAUDE_PROJECT_DIR', '/htb')
    import re
    m = re.search(r'machines/[^/]+', cwd)
    if m:
        log_dir = os.path.join(project_dir, m.group(), 'logs')
    else:
        log_dir = os.path.join(project_dir, 'logs')

    os.makedirs(log_dir, exist_ok=True)

    entry = {
        'action': command,
        'ts': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }

    log_path = os.path.join(log_dir, 'actions.jsonl')
    try:
        with open(log_path, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    except OSError:
        pass  # Don't block the command if logging fails

if __name__ == '__main__':
    main()
