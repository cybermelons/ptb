---
name: Pentest engine design decisions
description: Key design decisions and lessons from building pentest-engine/ orchestrator
type: project
---

The engine at pentest-engine/ runs Claude Code on rails via `claude -p` subprocess calls.

**Architecture:** Python loop → planner (picks task) → gates (validate) → executor (runs tools) → state update → loop.

**Key lessons (2026-04-07):**
- Planner needs comprehensive hint with ALL context (creds, IPs, tool paths, dead ends)
- Executor wastes tools on PATH discovery — include tool paths in hint
- Drift detection (10-tool limit, script rewrite detection, wall timeout 120s) prevents runaway executors
- LLM compaction (haiku) reduces 50KB state to ~5KB for planner — critical for speed
- evil-winrm broken in container — use crackmapexec winrm -x instead
- The engine eliminates paths; the operator notices patterns. Both are needed.
- scriptPath toggle triggers AD change notification → logon script fires (Garfield box)

**How to apply:** When launching engine, provide the fullest possible hint. Watch live.log during execution. Commit findings frequently.
