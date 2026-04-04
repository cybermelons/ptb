# Reporting

Goal: produce a clear, actionable record of every confirmed vulnerability.

## When To Write Findings

Immediately upon confirmation. Not at the end of the engagement. Not after you've tested three more things. The moment `conclusion` is `confirmed` in your hypothesis cycle, write to `findings.jsonl`.

## Finding Format

Every finding in `./state/findings.jsonl` must have all of these fields:

```json
{
  "id": "FINDING-NNN",
  "vuln": "CVE-2021-41773 or descriptive name if no CVE",
  "class": "path-traversal | sqli | rce | auth-bypass | info-disclosure | misconfig | privesc | cred-exposure | xss | ssrf | idor",
  "severity": "critical | high | medium | low | informational",
  "cvss": 9.8,
  "host": "10.0.0.5",
  "port": 8080,
  "path": "/cgi-bin/",
  "evidence_cmd": "the exact command you ran",
  "evidence_output": "the relevant output (truncate if over 10 lines, keep the proving lines)",
  "impact": "what an attacker could do with this — be specific and concrete",
  "remediation": "specific fix, not generic advice",
  "ts": "ISO 8601 timestamp"
}
```

## Severity Classification

Use CVSS 3.1 base score as the primary guide, but apply practical judgment:

- **Critical (9.0-10.0)**: unauthenticated RCE, full database access, domain admin compromise
- **High (7.0-8.9)**: authenticated RCE, significant data exposure, privilege escalation to root
- **Medium (4.0-6.9)**: XSS, CSRF, information disclosure with limited impact, non-sensitive IDOR
- **Low (0.1-3.9)**: verbose error messages, minor info leaks, missing headers with no exploitable impact
- **Informational (0.0)**: observations that aren't vulnerabilities but are worth noting (outdated but unaffected versions, unusual configs)

Don't inflate severity. A missing `X-Frame-Options` header is not "high" — it's low or informational unless you can demonstrate a concrete clickjacking impact.

## Evidence Standards

Your evidence must be reproducible. Someone reading the finding should be able to run your exact command and see the same result.

**Good evidence:**
- Exact command with all flags and parameters
- The specific output lines that prove the vulnerability
- Explanation of why this output confirms the vulnerability

**Bad evidence:**
- "The application was vulnerable to SQL injection" (no proof)
- A screenshot description without the actual command (not reproducible)
- Output from an automated scanner without manual verification

## Remediation Guidelines

Be specific. Not "update your software" but "upgrade Apache from 2.4.49 to >= 2.4.51 to patch CVE-2021-41773."

- Reference specific patch versions when a CVE exists
- If no patch exists, recommend mitigations (WAF rule, config change, network segmentation)
- Note if the remediation has dependencies or risks ("upgrading PHP may require testing application compatibility")

## Final Report

At the end of an engagement, produce a summary by reading `findings.jsonl`:

```bash
cat ./state/findings.jsonl | jq -s 'sort_by(.severity) | reverse'
```

Group by severity. Lead with critical/high findings. Include a summary count at the top.
