#!/usr/bin/env python3
"""Stop hook: when the agent is about to stop, check for unsaved state."""
import json, sys, os, glob

def main():
    data = json.load(sys.stdin)
    cwd = data.get('cwd', '')
    project_dir = os.environ.get('CLAUDE_PROJECT_DIR', '/htb')

    warnings = []

    # Check if there's a counter > 0 (agent stopping mid-cycle without checkpoint)
    try:
        with open('/tmp/.claude_action_counter') as f:
            count = int(f.read().strip())
        if count >= 5:
            warnings.append(
                f"Stopping with {count} actions since last checkpoint. "
                "Consider writing a checkpoint before ending."
            )
    except (OSError, ValueError):
        pass

    # Check for machine dirs with state/ but no recent findings
    machine_dirs = glob.glob(os.path.join(project_dir, 'machines', '*', 'state'))
    for state_dir in machine_dirs:
        surface = os.path.join(state_dir, 'surface.jsonl')
        tested = os.path.join(state_dir, 'tested.jsonl')
        unexplored = os.path.join(state_dir, 'unexplored.jsonl')

        # If we have tested hypotheses but no unexplored branches, flag it
        if os.path.exists(tested) and not os.path.exists(unexplored):
            machine = os.path.basename(os.path.dirname(state_dir))
            warnings.append(
                f"Machine '{machine}' has tested.jsonl but no unexplored.jsonl. "
                "Are there branches you forgot to queue?"
            )

    if warnings:
        output = {
            'decision': 'approve',
            'reason': ' | '.join(warnings),
        }
        json.dump(output, sys.stdout)

    sys.exit(0)

if __name__ == '__main__':
    main()
