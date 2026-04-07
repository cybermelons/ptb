---
name: Engine-operator split
description: The pentest engine executes and reports. The operator (Claude watching) correlates patterns across iterations. Don't make the engine smarter — make the operator more attentive.
type: feedback
---

The engine doesn't need to detect trigger mechanisms or correlate timing patterns. It executes, logs to live.log and orchestrator.jsonl, and reports structured results.

The operator watches logs and connects dots — like noticing a responder callback appeared right after the engine toggled a scriptPath attribute.

**Why:** The Garfield breakthrough came from noticing a timing correlation between engine actions and responder output. The engine can't do this (stateless iterations). The operator can (full timeline view).

**How to apply:** When running the engine, actively watch live.log + responder/listener output in parallel. Don't just wait for structured verdicts — watch RAW side effects.
