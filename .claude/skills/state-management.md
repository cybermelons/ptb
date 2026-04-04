# State Management

All state is append-only JSONL. Never edit or rewrite existing lines. Only append.

## Why Append-Only

Rewriting JSON objects causes silent data loss — you'll drop fields you didn't think were important. Appending one line is near-zero risk. When you need a current picture, read the full file and synthesize.

## Files and Schemas

### `./state/surface.jsonl` — discoveries

Each line is one thing you found. Always include `type`, `discovered_by`, and `ts`.

```json
{"type":"host","ip":"10.0.0.5","hostname":"web01.internal","discovered_by":"nmap -sn","ts":"2025-01-15T09:30:00Z"}
{"type":"service","ip":"10.0.0.5","port":8080,"proto":"tcp","service":"http","product":"Apache","version":"2.4.49","discovered_by":"nmap -sV","ts":"2025-01-15T09:31:00Z"}
{"type":"tech","ip":"10.0.0.5","port":8080,"tech":"PHP 7.4","discovered_by":"response header X-Powered-By","ts":"2025-01-15T09:35:00Z"}
{"type":"directory","ip":"10.0.0.5","port":8080,"path":"/admin","status":403,"discovered_by":"gobuster","ts":"2025-01-15T09:40:00Z"}
{"type":"dns","record":"A","name":"mail.target.com","value":"10.0.0.10","discovered_by":"dig","ts":"2025-01-15T09:42:00Z"}
```

Valid types: `host`, `service`, `tech`, `directory`, `dns`, `cert`, `header`, `user`, `config`

### `./state/tested.jsonl` — hypotheses tested

```json
{"hypothesis":"Apache 2.4.49 on 10.0.0.5:8080 vulnerable to CVE-2021-41773","action":"curl http://10.0.0.5:8080/cgi-bin/.%2e/%2e%2e/etc/passwd","conclusion":"confirmed","evidence":"returned /etc/passwd contents","ts":"2025-01-15T09:45:00Z"}
{"hypothesis":"SSH on 10.0.0.5:22 allows password auth","action":"ssh -o PreferredAuthentications=password -o BatchMode=yes test@10.0.0.5","conclusion":"confirmed","evidence":"prompted for password, not rejected","ts":"2025-01-15T09:50:00Z"}
```

`conclusion` must be exactly one of: `confirmed`, `denied`, `inconclusive`

When `conclusion` is `denied`, add `block_type` and `why`:
- `"block_type":"soft","why":"payload syntax wrong, need URL encoding"` — retry with fix
- `"block_type":"hard","why":"FAKEPC$ lacks TRUSTED_FOR_DELEGATION, requires domain admin to set"` — pivot immediately

### `./state/unexplored.jsonl` — branch backlog

```json
{"branch":"check SSH weak creds on 10.0.0.5:22","rationale":"OpenSSH 7.6, password auth enabled","priority":"medium","added":"2025-01-15T09:50:00Z"}
```

`priority` must be: `critical`, `high`, `medium`, `low`

### `./state/creds.jsonl` — credentials

```json
{"id":"cred-001","type":"password","username":"admin","secret":"[write actual value here]","source":"/var/www/.env on 10.0.0.5","host":"10.0.0.5","ts":"2025-01-15T10:00:00Z"}
```

Always assign a sequential ID. Reference by ID in conversation — don't repeat secrets in chat messages.

### `./state/findings.jsonl` — confirmed vulnerabilities

```json
{"id":"FINDING-001","vuln":"CVE-2021-41773","class":"path-traversal","severity":"critical","cvss":9.8,"host":"10.0.0.5","port":8080,"path":"/cgi-bin/","evidence_cmd":"curl http://10.0.0.5:8080/cgi-bin/.%2e/%2e%2e/etc/passwd","evidence_output":"root:x:0:0:root:/root:/bin/bash ...","impact":"unauthenticated file read, potential RCE via mod_cgi","remediation":"upgrade Apache to >= 2.4.51","ts":"2025-01-15T09:45:00Z"}
```

### `./logs/actions.jsonl` — audit trail

Log BEFORE executing. Every command, no exceptions.

```json
{"action":"nmap -sV -p 1-1000 10.0.0.5","phase":"enumeration","hypothesis":"identify services on top 1000 ports","ts":"2025-01-15T09:30:00Z"}
```

## Reading State

Before any phase transition or full decision cycle, read the relevant state files:

```bash
# Current attack surface
cat ./state/surface.jsonl | jq -s 'group_by(.ip) | map({host: .[0].ip, findings: .})'

# What's been tested
cat ./state/tested.jsonl | jq -s 'map(select(.conclusion == "inconclusive"))'

# Outstanding branches
cat ./state/unexplored.jsonl | jq -s 'sort_by(.priority)'
```

If a state file doesn't exist yet, create it on first write. Don't error on missing files during reads — just treat as empty.
