# Environment

Running inside an isolated Kali Linux Docker container.

**Authorization:** All targets are Hack The Box lab machines — legal and authorized.

## Credentials

- `$GITHUB_TOKEN` — GitHub PAT, available as env var inside the container

## Network

- OpenVPN tunnel to HTB lab — start with `sudo openvpn --config <file> --daemon --log /tmp/openvpn.log --pull-filter ignore "ifconfig-ipv6" --pull-filter ignore "route-ipv6" --pull-filter ignore "tun-ipv6"`
- Outbound internet available via Docker bridge NAT

## Installed tools

nmap, gobuster, feroxbuster, nikto, sqlmap, python3, pip, curl, wget, git, net-tools, dnsutils

Additional tools installable at runtime via `apt` or `pip`.

## Workspace

- Workdir: `/htb` (repo bind-mounted from host)
- Each box has a workspace under `machines/<name>/`
- Save scans to `scans/`, scripts to `exploits/`
- `notes.md` — chronological worklog of commands, results, dead ends, pivots
- `report.md` — polished final writeup with attack chain, creds, flags, postmortem
## Methodology

Recon → Enumerate → Exploit → Survey → Privesc → Report.
Commit continuously: after each phase, each dead end, each new finding, and every 10-15 minutes. Don't batch — small commits as you go.
Survey (post-shell checklist) comes BEFORE privesc. Always.

## notes.md — Worklog

The running worklog. Append-only, chronological, raw:

```
## 09:15 — Recon
- `nmap -sC -sV` → ports 21,22,80,8080 open
- FTP anonymous → found employee-service.jar

## 09:25 — Trying CXF SSRF
- Sent MTOM XOP:Include → got callback on listener. SSRF confirmed.
- Read /etc/passwd → found dev_ryan user
- Read hoverfly.service → creds admin:O7IJ27MyyXiU

## 09:35 — Dead end: Hoverfly file read CVE
- Tried CVE-2024-45388 → "relative path is invalid". Patched. Moving on.
```

Small commits: `notes: tried XXE, blocked` > one giant commit at the end.

## Post-Shell Checklist

Run ALL of these IMMEDIATELY after getting any new shell. Survey before you exploit.

1. `ls -la ~` and `find ~ -type f` — look at what's already here
2. `sudo -l` — sudo privileges
3. `id && groups` — group memberships
4. `cat /etc/passwd | grep sh$` — users with shells
5. `systemctl list-timers --all` — systemd timers (cron equivalent)
6. `ss -tlnp` — internal services
7. `find / -writable -type f ! -path '/proc/*' ! -path '/sys/*' 2>/dev/null` — writable files
8. `getfacl <target dirs>` — ACLs beyond standard permissions
9. `cat /etc/crontab; ls /etc/cron.d/` — cron jobs
10. `find / -perm -4000 -type f 2>/dev/null` — SUID binaries
11. `grep -i passwordauth /etc/ssh/sshd_config` — can users SSH with passwords?
12. `ls -la /home/` — who has home dirs, what perms?

Log results in notes.md. Commit. THEN start privesc.

## Decision Trees — MANDATORY, not optional

### Got initial RCE (webshell)?
```
1. Is the shell clean (<1KB response)?
   NO  → Deploy a clean shell FIRST. Never enumerate through a broken/slow/binary shell.
         A 30-second detour to write a tiny shell saves hours.
   YES → Continue.
2. ALWAYS use 2>&1 on every command. Empty output = check stderr, not retry.
3. ALWAYS use --connect-timeout 3 --max-time 8 on curl/wget. No hanging.
4. Run post-shell checklist (below).
5. Commit notes.
```

### Got LFI / file read?
```
1. Read /etc/passwd → list users with shells
2. Read /etc/ssh/sshd_config → is PasswordAuthentication enabled?
3. Read app source code (web apps, scripts, configs)
4. Read /etc/shadow (usually fails but TRY — some boxes have weak perms)
5. Read SSH keys: /home/<user>/.ssh/id_rsa, id_ed25519
6. Read git repos: .git/config, git log for credentials in history
7. Read process info: /proc/self/environ, /proc/self/cmdline
8. Read cron: /etc/crontab, /var/spool/cron/crontabs/<user>
```

### Got file write primitive?
```
1. Get a SHELL, not a flag. Write access = real shell (SSH key, webshell, cron). Do that first.
2. Can you write to a web root? → Write a webshell (.php, .jsp, .aspx)
3. Can you write to a user's ~/.ssh/? → Write authorized_keys
4. Can you write to cron dirs? → Write a cron job (but check filename rules)
5. Can you write to /etc/? → passwd, shadow, sudoers.d (if writable)
6. Can you control the OUTPUT path of a process? → Check if output naming is validated
7. Input validation ≠ output validation. Bypass might be on the output side.
```

### Got SUID binary as another user?
```
1. Can you write to their home directory?
   YES → Plant SSH key. mkdir -p ~/.ssh, write authorized_keys. SSH in. DONE.
         DO NOT try to read files through SUID bash. Get a real shell first.
   NO  → Check what you CAN write. /tmp? Cron dirs? Config files?
2. SSH gives you real uid+gid. SUID only gives euid (not egid).
   Files owned by root with group=targetuser need egid, not euid.
   SSH solves this. SUID doesn't.
```

### Got credentials for a user?
```
1. Try SSH first (even if you think it's key-only — CHECK sshd_config).
2. Try su from existing shell.
3. Try on web portals, databases, other services.
4. Try password reuse on other users.
```

### Command returns empty?
```
1. Add 2>&1. Read stderr.
2. "Permission denied" → understand WHY (check owner, group, perms, ACLs).
3. "Command not found" → check PATH, use full path.
4. Still empty → check if output went to a file (redirect conflict).
   shell_exec("cmd > /tmp/x.txt 2>&1 > /tmp/o.txt") = redirect conflict.
   Use ONE redirect only.
```

### New box / IP change?
```
1. WIPE old entries from /etc/hosts first. grep -v hostname /etc/hosts > /tmp/h && sudo cp /tmp/h /etc/hosts
2. Add ONE entry for new IP.
3. Verify: curl --connect-timeout 3 http://hostname/ 
4. If curl hangs but ping works → check /etc/hosts for stale entries.
```

### Source code available?
```
1. READ IT FIRST. Trace the exact execution path.
2. Check what the code PRODUCES (output paths), not just what it accepts (input validation).
3. Input checks ≠ output checks. Bypass might be on the output side.
```

### Box dropped mid-exploit?
```
1. Was the exploit already running and returned output?
   YES → It didn't "get interrupted." It FAILED. Analyze the output before retrying.
   NO  → Connection issue. Continue to step 2.
2. Stop doing things step-by-step. Write a SCRIPT that:
   - Polls for box connectivity
   - Runs the full exploit chain on reconnect
   - Grabs the flag
3. Use the downtime to verify your approach (read library source, check assumptions).
```

### Stuck for 15+ minutes on one approach?
```
1. STOP executing. Write in notes: what am I trying, why is it failing.
2. 3-strike rule: same goal failed 3 times? The GOAL may be wrong, not just the method.
3. Read notes from the beginning. Look for patterns.
4. Ask: "What's the simplest path to a REAL SHELL as this user?"
   Not "how do I read this one file" — get the shell, everything follows.
5. Check: am I trying to READ when I should WRITE?
   am I trying to EXPLOIT when I should ENUMERATE?
   am I trying variations of the SAME thing?
```
