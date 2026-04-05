# Pterodactyl — 10.129.18.36 — PWNED

## Timeline

### 23:27 — Recon
- nmap → ports 22 (SSH), 80 (HTTP/nginx)
- Redirect to pterodactyl.htb, vhost enum found panel.pterodactyl.htb
- changelog.txt: Pterodactyl Panel v1.11.10, PHP-PEAR, register_argc_argv=On
- phpinfo.php: PHP 8.4.8, no disable_functions, no open_basedir

### 23:30 — CVE-2025-49132: LFI → RCE as wwwrun
- /locales/locale.json LFI + pearcmd.php config-create
- Two-stage: write webshell to /tmp, include via LFI
- Shell as wwwrun (uid 474)

### 23:34 — Post-shell survey
- openSUSE Leap 15.6, kernel 6.4.0
- Users: headmonitor (uid 1001, admin), phileasfogg3 (uid 1002)
- Services: SSH, HTTP, PHP-FPM, MariaDB, Redis, Postfix, cron
- Wings/Docker: inactive

### 23:38 — Database dump
- .env → pterodactyl:PteraPanel for MariaDB
- Panel users + bcrypt hashes extracted
- Wings daemon token from /etc/pterodactyl/config.yml

### 23:52 — Password cracking → SSH
- john + rockyou cracked phileasfogg3: !QAZ2wsx
- SSH as phileasfogg3 works
- User flag: 793c17584147b8c0c46db1f6bb2e8619

### 23:53–00:15 — Privesc investigation
- sudo (ALL) ALL with targetpw — need root's password
- Mail hint: udisksd unusual activity → CVE-2025-6018/6019
- PAM bypass (.pam_environment) sets Seat=seat0 but polkit returns 'challenge'
- Discovery: polkit-default-privs package has custom JS rule checking subject.local
- subject.local=false for Remote=true sessions (SSH always Remote)

### 00:15–00:30 — Solving the local session problem
- objdump confirms polkitd only uses sd_session_get_seat + sd_session_is_active
- BUT 90-default-privs.rules JS checks subject.local (Remote flag)
- chkstat-polkit Perl script generates JS: `if (subject.local) { i=2 } else { i=0 }`
- Solution: su from wwwrun RCE (local process, no PAM_RHOST) → Remote=false

### 00:30–03:59 — CVE-2025-6019 exploitation
- Zombie session management: lingering su processes block new session creation
- XFS image creation: mkfs.xfs min 300MB, extended to 500MB via truncate
- xfs_db to set root ownership + SUID on bash binary in unmounted image
- Resize race: libblockdev mounts at /tmp/blockdev.XXXXXX without nosuid
- Unmount failed ("target is busy") → mount persisted!
- /tmp/blockdev.8BEPN3/xpl: -rwsr-xr-x root root → euid=0

### 03:59 — ROOT
- Root flag: b37cfd3270364eef476ed089f0d38b7a

## Dead Ends
- Redis CONFIG SET dir/dbfilename: protected, can't write arbitrary files
- headmonitor bcrypt hash: not cracked with rockyou
- SSH to localhost: still Remote=true (PAM_RHOST set by SSH regardless)
- Docker/Wings: both inactive, can't use for container escape
- su from SSH: doesn't create new logind session (inherits SSH session)
- Disk space: /tmp on 6GB root partition nearly full, used /dev/shm instead
