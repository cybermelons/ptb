#!/usr/bin/env python3
"""PreToolUse hook on Bash: logs every command to actions.jsonl before execution."""
import json, sys, os, re
from datetime import datetime, timezone

SKIP = ('git ', 'ls', 'cat ./state/', 'cat ./logs/', 'pwd', 'cd ', 'mkdir ', 'chmod ')

def main():
    data = json.load(sys.stdin)
    command = data.get('tool_input', {}).get('command', '')
    cwd = data.get('cwd', '')

    if any(command.startswith(p) for p in SKIP):
        sys.exit(0)

    project_dir = os.environ.get('CLAUDE_PROJECT_DIR', '/htb')
    m = re.search(r'machines/[^/]+', cwd)
    log_dir = os.path.join(project_dir, m.group(), 'logs') if m else os.path.join(project_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)

    entry = {
        'action': command,
        'ts': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }

    try:
        with open(os.path.join(log_dir, 'actions.jsonl'), 'a') as f:
            f.write(json.dumps(entry) + '\n')
    except OSError:
        pass

    sys.exit(0)

if __name__ == '__main__':
    main()
