# VariaType — 10.129.17.22 (originally 10.129.244.202)

## Box Status: www-data shell achieved, steve privesc STUCK

## Attack Chain (completed)
1. Git dump on portal (.git exposed) → `gitbot:G1tB0t_Acc3ss_2025!`
2. Portal LFI (download.php `....//` bypass via `f=` param) → read Flask app.py
3. Designspace format 5.0 `<variable-font filename="...">` → output path traversal
4. PHP polyglot font (PHP in name table platformID=1) written as cmd.php → **RCE as www-data**

## Webshell Usage
- cmd.php is a binary font with embedded PHP — outputs are mixed with ~700KB of binary
- Use redirect pattern: `cmd.php?cmd=COMMAND > /tmp/o.txt 2>&1` then read via LFI
- DO NOT add redirect in a wrapper — it conflicts with the command's own redirects
- File writes to /files/ work via: write to /tmp first, then `cp /tmp/file /var/www/.../files/`

## Critical Files Found
- `/opt/process_client_submissions.bak` — FULL source of steve's font processing script
- `/opt/font-tools/install_validator.py` — likely root privesc (setuptools PackageIndex RCE)
- `/usr/local/src/fontforge/` — full fontforge source code on the box
- `/usr/lib/python3.11/sitecustomize.py` — system sitecustomize imports `apport_python_hook`

## Steve's Processing Script (from backup)
```
- Runs as steve via cron (interval unknown — ran ~50 min after boot on one instance)
- cd /var/www/portal.variatype.htb/public/files/
- Iterates: *.ttf *.otf *.woff *.woff2 *.zip *.tar *.tar.gz *.sfd
- Filename regex: ^[a-zA-Z0-9._-]+$ (quarantines invalid names)
- For each file: fontforge -lang=py -c "...font = fontforge.open('$file')..."
- $file is bash-expanded in double quotes, Python string uses single quotes
- After processing: mv $file ~/processed_fonts/
- set -euo pipefail, but fontforge errors caught by if/then
```

## What DOES NOT work for www-data → steve

### Python module hijack from CWD — DEAD
- fontforge uses Py_Initialize() with no flags
- sys.path[0] = '' (CWD) IS set
- BUT: system `/usr/lib/python3.11/sitecustomize.py` already exists → shadows our CWD version
- System sitecustomize imports `apport_python_hook` (doesn't exist on system)
- Our apport_python_hook.py in CWD is NEVER imported during Python init
- Tested: even `python3 -c "print(42)"` from /files/ CWD does NOT load our apport_python_hook.py
- usercustomize.py also not loaded
- **Conclusion: Python module hijacking from CWD does not work during Py_Initialize()**

### SFD PickledData — DEAD
- fontforge stores PickledData as raw string: "It's a string of pickled data which we leave as a string"
- Never calls pickle.loads() during open()
- Deserialization only on explicit font.persistent access (which the -c script never does)

### SFD system() call — DEAD
- system() in sfd.c line 3332 is in the SAVE function (compression), not LOAD
- Not triggered by fontforge.open()

### Filename injection — DEAD
- Regex [a-zA-Z0-9._-] blocks all shell/Python special chars
- No single quote, no $, no backtick, no semicolon, no pipe

### fontforge hooks — NOT TESTED FULLY
- fontforge has `hooks["loadFontHook"]` called on font load (python.c line 19974)
- BUT hooks are set via Python code, not via SFD file content
- The -c script doesn't set any hooks before calling open()

## What MIGHT work (untried or partially tried)

### 1. SFD format — other executable fields?
- Checked: PickledData (no), system() (save only), Script (font metadata, not code)
- NOT checked: are there OTHER SFD fields that trigger Python or shell execution during open()?
- The SFD parser (sfd.c) is ~6000 lines. Needs more thorough review.

### 2. fontforge CVE for crafted font → RCE
- Version: 20230101, built 2025-12-07 from git a1dad3e
- Needs research: are there CVEs in this version that allow code execution via crafted font?
- This would be the "intended" path if the box is about font processing

### 3. pyhook/ directory in fontforge source
- /usr/local/src/fontforge/pyhook/ exists — what is it?
- Maybe fontforge loads Python hooks from a pyhook directory?
- If /files/pyhook/ or similar gets loaded...

### 4. fontforge.open() with SFD — does it run embedded Python?
- SFD format spec might have Python scripting sections we missed
- Check: FontForge documentation for SFD format Python embedding

### 5. Race condition in the processing script
- Script runs fontforge then mv. Between these, we could swap the file.
- Tight timing. Probably not the intended path.

### 6. Skip steve entirely — go www-data → root?
- install_validator.py needs euid=0 (checks explicitly)
- No SUID, no sudoers entries for www-data
- No sudo NOPASSWD for www-data
- Probably need steve first

## install_validator.py (root privesc — for AFTER getting steve)
```python
from setuptools.package_index import PackageIndex
index = PackageIndex()
downloaded_path = index.download(plugin_url, PLUGIN_DIR)
```
- PackageIndex.download() is known for arbitrary code execution
- Downloads from user-supplied URL, can execute setup.py in archives
- Script checks os.geteuid() != 0 — needs sudo
- Steve likely has sudo for this script
- Exploit: host malicious .tar.gz with setup.py containing reverse shell

## System Info
- Debian 12 (bookworm), kernel 6.1.0-43-amd64
- nginx 1.22.1, PHP 8.2, Python 3.11
- fontforge 20230101 at /usr/local/src/fontforge/build/bin/fontforge
- Users: steve (1000), variatype (102, group www-data), www-data (33)
- variatype service: ReadWritePaths=/var/www/.../files + /opt/variatype
- Portal: /var/www/portal.variatype.htb/public/ (drwxrwsr-x www-data:www-data)
- Flask: /opt/variatype/app.py, port 5000

## Credentials
- gitbot:G1tB0t_Acc3ss_2025! (portal login)
- Flask SECRET_KEY: 7e052f614c5f9d5da3249cc4c6d9a950053aed370b8464d2e8a81d41ff0e3371
