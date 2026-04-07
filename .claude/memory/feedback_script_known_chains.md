---
name: Script known chains — don't re-run confirmed sequences through the engine
description: Once an attack chain is confirmed, write a bash script and replay it. Don't burn LLM tokens on deterministic steps.
type: feedback
---

When an attack chain is confirmed (every step tested and working), IMMEDIATELY write a replay script. Don't feed known steps back through the engine iteration by iteration.

**Why:** On Garfield, the scriptPath → l.wilson_adm → RODC01$ → root chain was confirmed but kept getting re-run through the engine on fresh instances, wasting 10+ iterations of LLM tokens on deterministic commands that should have been a 20-line bash script.

**How to apply:**
1. Before launching the engine, check: "do I already know what to do?" If yes, write a script.
2. The engine is for DISCOVERY. Scripts are for REPLAY.
3. When the engine confirms a step, append it to `exploits/chain.sh` immediately.
4. On fresh instances, run the script for known steps, engine for unknown steps.
5. If you catch yourself giving the engine a hint with exact commands — that's a script, not an engine task.
