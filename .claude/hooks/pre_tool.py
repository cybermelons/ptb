#!/usr/bin/env python3
"""PreToolUse hook on Bash: enforce hypothesis-driven reasoning.

Three gates:
  1. Hypothesis Registration — exploitation commands require a documented hypothesis
  2. Grind Detection — block after 5 exploit commands without updating state
  3. Hard Block Re-entry — prevent retrying structurally dead techniques

Also logs every non-trivial command to actions.jsonl (existing functionality).
"""
import json, sys, os, re, time
from datetime import datetime, timezone

# --- Command classification ---

# Always free — housekeeping, state management, git
FREE_PATTERNS = (
    'git ', 'ls', 'cat ', 'pwd', 'cd ', 'mkdir ', 'chmod ', 'echo ',
    'cp ', 'mv ', 'touch ', 'head ', 'tail ', 'wc ', 'file ',
    'which ', 'type ', 'man ', 'help',
    'apt', 'pip', 'pip3',
)

# Recon — exploratory, no hypothesis required
RECON_PATTERNS = (
    'nmap', 'gobuster', 'feroxbuster', 'nikto', 'dirb',
    'dig ', 'host ', 'nslookup', 'whois',
    'enum4linux', 'smbclient', 'rpcclient', 'ldapsearch',
    'crackmapexec', 'netexec', 'kerbrute',
    'ping ', 'traceroute', 'nc -z', 'ss ', 'netstat',
    'ip ', 'ifconfig', 'id', 'whoami', 'hostname', 'uname',
    'ps ', 'ps aux',
)

# State writes — always free AND reset grind counter
STATE_WRITE_PATTERNS = (
    'state/', 'logs/', 'notes.md', 'tested.jsonl',
    'surface.jsonl', 'unexplored.jsonl', 'findings.jsonl',
    'creds.jsonl', 'checkpoint.md', 'hypothesis',
)

STATE_FILE = '/tmp/.claude_reasoning_state.json'
GRIND_LIMIT = 5


def classify_command(cmd):
    """Classify a command as 'free', 'recon', 'state_write', or 'exploit'."""
    stripped = cmd.strip()

    # State writes — check if command writes to state files
    for pat in STATE_WRITE_PATTERNS:
        if pat in stripped:
            # Must be a write, not just a read
            if any(w in stripped for w in ('>>', '>', 'tee ', 'write', 'echo ', 'cat <<', 'python3 -c')):
                return 'state_write'
            # Also catch explicit file creation to state dirs
            if stripped.startswith(('echo ', 'cat <<', 'python3 -c', 'printf ')):
                return 'state_write'

    # Free commands
    for pat in FREE_PATTERNS:
        if stripped.startswith(pat):
            return 'free'

    # Recon commands
    for pat in RECON_PATTERNS:
        if stripped.startswith(pat):
            return 'recon'

    # Everything else is exploitation
    return 'exploit'


def load_state():
    """Load reasoning state, return defaults if missing."""
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {
            'current_hypothesis': None,
            'hypothesis_set_at': None,
            'commands_since_state_write': 0,
            'hard_blocks': [],
            'phase': 'recon',
        }


def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)


def check_hard_blocks(cmd, hard_blocks):
    """Check if command matches any hard-blocked technique category."""
    cmd_lower = cmd.lower()
    for block_entry in hard_blocks:
        # block_entry format: "keyword:reason" or just "keyword"
        keyword = block_entry.split(':')[0].strip().lower()
        # Split keyword into words for fuzzy matching
        keywords = keyword.split('_')
        if all(kw in cmd_lower for kw in keywords if len(kw) > 2):
            return block_entry
    return None


def log_action(cmd, cwd):
    """Log command to actions.jsonl (existing functionality)."""
    project_dir = os.environ.get('CLAUDE_PROJECT_DIR', '/htb')
    m = re.search(r'machines/[^/]+', cwd)
    log_dir = os.path.join(project_dir, m.group(), 'logs') if m else os.path.join(project_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    entry = {
        'action': cmd[:200],
        'ts': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }
    try:
        with open(os.path.join(log_dir, 'actions.jsonl'), 'a') as f:
            f.write(json.dumps(entry) + '\n')
    except OSError:
        pass


def block(msg):
    """Block the command — exit 2, message to stderr."""
    sys.stderr.write(msg + '\n')
    sys.exit(2)


def session_log(cmd, cwd, session_id):
    """Unconditional append-only session log. Every command, no exceptions.
    Logs to machines/<box>/logs/session_<id>.jsonl so each box and session is separate."""
    project_dir = os.environ.get('CLAUDE_PROJECT_DIR', '/htb')
    m = re.search(r'machines/[^/]+', cwd)
    if m:
        log_dir = os.path.join(project_dir, m.group(), 'logs')
    else:
        log_dir = os.path.join(project_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f'session_{session_id}.jsonl') if session_id else os.path.join(log_dir, 'session.jsonl')
    try:
        with open(log_file, 'a') as f:
            f.write(json.dumps({
                'ts': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                'cwd': cwd,
                'cmd': cmd,
            }) + '\n')
    except OSError:
        pass


def main():
    data = json.load(sys.stdin)
    cmd = data.get('tool_input', {}).get('command', '')
    cwd = data.get('cwd', '/htb')
    session_id = data.get('session_id', '')

    # Unconditional session log — full audit trail, LLM-independent
    session_log(cmd, cwd, session_id)

    category = classify_command(cmd)

    # State writes: always free, reset grind counter
    if category == 'state_write':
        state = load_state()
        state['commands_since_state_write'] = 0
        save_state(state)
        sys.exit(0)

    # Free and recon: always allowed, just log
    if category in ('free', 'recon'):
        if category != 'free':
            log_action(cmd, cwd)
        sys.exit(0)

    # --- Exploitation command: enforce gates ---
    state = load_state()
    log_action(cmd, cwd)

    # Gate 3: Hard block re-entry
    matched_block = check_hard_blocks(cmd, state.get('hard_blocks', []))
    if matched_block:
        block(
            f"HARD BLOCK VIOLATION: \"{matched_block}\" was classified as structurally impossible.\n"
            f"To retry this category, first log to state WHY the block no longer applies.\n"
            f"Write new information to ./state/tested.jsonl, then retry."
        )

    # Gate 1: Hypothesis registration
    if not state.get('current_hypothesis'):
        block(
            "HYPOTHESIS REQUIRED: You're running an exploitation command without a documented hypothesis.\n"
            "Before proceeding, register your hypothesis:\n"
            "  echo '{\"hypothesis\":\"YOUR CLAIM\",\"disproof\":\"WHAT WOULD PROVE IT WRONG\"}' >> ./state/tested.jsonl\n"
            "Or write it to notes.md. Then update /tmp/.claude_reasoning_state.json with current_hypothesis.\n"
            "Recon commands (nmap, gobuster, etc.) don't require this."
        )

    # Gate 2: Grind detection
    state['commands_since_state_write'] = state.get('commands_since_state_write', 0) + 1
    save_state(state)

    if state['commands_since_state_write'] > GRIND_LIMIT:
        state['commands_since_state_write'] = 0
        save_state(state)
        block(
            f"GRIND LIMIT: {GRIND_LIMIT} exploitation commands on hypothesis "
            f"\"{state.get('current_hypothesis', '?')}\" without updating state.\n"
            f"You must do ONE of:\n"
            f"  1. Log result to ./state/tested.jsonl (confirmed/denied/inconclusive)\n"
            f"  2. Update hypothesis (write new entry, then continue)\n"
            f"  3. Log hard block and pivot\n"
            f"Writing to state resets the counter."
        )

    sys.exit(0)


if __name__ == '__main__':
    main()
