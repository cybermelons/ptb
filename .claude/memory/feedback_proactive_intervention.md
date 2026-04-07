---
name: Proactive intervention — don't just watch the engine fail
description: If you know the engine will fail or know the result, STOP it immediately and act on that knowledge. Don't watch it burn tokens on a predictable failure.
type: feedback
---

When operating the engine, actively predict outcomes. If you KNOW:
- A password is wrong → stop, fix the hint, don't watch it fail
- A tool won't be found → stop, install it first or give the full path
- A gate will reject → stop, fix the gate or bypass it
- The approach won't work → stop, steer differently
- The steps are already known → don't use the engine at all, write a script

**Why:** On Garfield, watched the engine fail 5+ times on the same AES key issue, wrong passwords, PATH issues, and gate rejections — each time burning a full iteration of tokens before intervening. Should have stopped and corrected after the FIRST failure.

**How to apply:** After each engine iteration, ask: "Do I know what will happen next?" If yes, intervene before it happens. The engine is for discovery, not for confirming what you already know.
