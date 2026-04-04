# Handling Ambiguity

Tool output is messy. Your job is to disambiguate, not guess.

## General Rule

One disambiguating probe. If still unclear, mark `inconclusive` in `tested.jsonl`, log what you tried, move to next branch. Don't burn more than 2 actions on a single ambiguous result.

## Specific Situations

### Filtered Ports (nmap)

"Filtered" means a packet went out and nothing came back. Could be firewall, could be timeout, could be rate limiting.

- Try a different scan technique: `-sA` (ACK) can sometimes distinguish filtered from firewalled
- Try a different timing: `--scan-delay 1s` if rate limiting is suspected
- Try from a different source port: `--source-port 53` or `--source-port 80`
- If still filtered after one retry, mark inconclusive and move on. Don't run 5 different scan types.

### HTTP 403 Forbidden

Could mean: authentication required, WAF blocking, IP deny list, real access denial, or directory exists but listing is disabled.

Disambiguation steps (try ONE, not all):
- Different User-Agent: `curl -H "User-Agent: Mozilla/5.0" <url>`
- Different HTTP method: `curl -X OPTIONS <url>`, `curl -X HEAD <url>`
- Path case variation: `/Admin` vs `/admin` vs `/ADMIN`
- Check if 403 applies to subdirectories: `<url>/test` — if that's 404, the parent directory exists

A 403 is still valuable — log it to `surface.jsonl`. It confirms the path exists.

### HTTP Timeouts

- Retry once with a longer timeout: `curl --max-time 30`
- If still timing out, check if other ports/services on the same host respond — the host might be down
- If the host is otherwise responsive, note the timeout and move on — might indicate a slow backend worth revisiting later
- Don't retry more than once

### Partial Version Strings

"Apache 2.4" without a patch level, "OpenSSH 7.x", "PHP 7" — not specific enough to pick a CVE.

- Check full HTTP headers: `curl -sI <url>` — sometimes the full version is in Server or X-Powered-By
- Check error pages: trigger a 404 or 500, frameworks often reveal version in error output
- Check `/server-info` or product-specific version endpoints
- If you still can't get a full version, log what you have and test for vulnerability classes (e.g., common misconfigs) rather than specific CVEs

### Inconsistent Results

Running the same command twice gives different output. Could be: load balancer, WAF with rate limiting, dynamic content, or race condition.

- Run 3-5 times and note the pattern
- Check for load balancer indicators: `Host` header variations, different `Server` headers across requests
- If behind a load balancer, note in `surface.jsonl` — you might be testing different backends

### "Success" That Might Not Be

Some apparent wins are false positives:
- SQL injection: an error message doesn't mean injection — it might be input validation
- Path traversal: getting a response doesn't mean you read the file — check if the content is actually `/etc/passwd` or a custom error
- Command injection: timing-based detection can be thrown off by network latency — confirm with a second timing payload (e.g., `sleep 3` after `sleep 5`)

Always verify before writing to `findings.jsonl`. A finding must be confirmed, not just "probably."

## Decision Trees

### Command returns empty?
```
1. Add 2>&1. Read stderr.
2. "Permission denied" → understand WHY (check owner, group, perms, ACLs).
3. "Command not found" → check PATH, use full path.
4. Still empty → check if output went to a file (redirect conflict).
   shell_exec("cmd > /tmp/x.txt 2>&1 > /tmp/o.txt") = redirect conflict.
   Use ONE redirect only.
```
