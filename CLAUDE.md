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
- Methodology: recon > enum > exploit > privesc > post

## Worklog Discipline

`notes.md` is the running worklog. Keep it updated throughout the engagement:

- Every significant command and a 1-line result summary
- Dead ends: what you tried, why it failed, what you learned
- Pivots: when you change approach and why
- Raw and chronological — don't revise, just append

`report.md` is written at the end: polished attack chain, creds, flags, postmortem.

**When to commit:**
- After completing each logical phase (recon done, got user shell, etc.)
- After hitting a dead end and pivoting — commit the attempt before moving on
- Before stopping for any reason
- Roughly every 10-15 minutes of active work

**Commit style:** Small, frequent commits. `notes: tried XXE on CXF, blocked by input validation` is better than one giant commit at the end.

## Post-Shell Checklist

Run these IMMEDIATELY after getting any new shell, before attempting complex exploits:
1. `ls -la ~` and `find ~ -type f` — backups, zips, source code, notes
2. `sudo -l` — sudo privileges
3. `id && groups` — group memberships
4. `systemctl list-timers --all` — systemd timers
5. `find / -writable -type f ! -path '/proc/*' ! -path '/sys/*' 2>/dev/null` — writable files
6. `getfacl <target dirs>` — ACLs beyond standard permissions
7. `ss -tlnp` — internal services

Time-box each exploitation approach to 15 minutes. If stuck, re-enumerate.
