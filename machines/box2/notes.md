# variatype.htb — 10.129.244.202

## Recon

### 10:14 — Port scan
- 22/tcp SSH OpenSSH 9.2p1 Debian
- 80/tcp nginx 1.22.1 → redirects to http://variatype.htb/
- Only 2 ports. TTL=63 → Linux (Debian 12)

### 10:15 — Web app
- VariaType Labs — Variable Font Generator
- Pages: /, /services, /tools/variable-font-generator
- Upload form at /tools/variable-font-generator: accepts .designspace (XML) + .ttf/.otf masters
- Posts to /tools/variable-font-generator/process
- Uses fonttools/fontmake (Python) for processing
- No auth required
- test.variatype.htb returns 301 (different vhost exists?)

## Enumeration

### 10:16 — Directory brute (variatype.htb)
- Only found: /, /services, /tools/variable-font-generator, /static/css/corporate.css
- No hidden endpoints on main site

### 10:16 — Vhost enumeration
- Found: **portal.variatype.htb** — Internal Validation Portal
- Login form: username + password, POST to /
- "Typography Integrity & Document Validation Suite"
- Version ref: VT-VALID-2.1.4
- IT support: it-support@variatype.internal
- "All processing occurs locally. No external data transmission."

### 10:17 — Portal enumeration
- **`.git` directory EXPOSED!** HEAD, config, index all accessible
- Portal is PHP (PHPSESSID cookie)
- /index.php — login page
- /files/ — directory listing (301)
- /styles.css — CSS file
- Default creds admin:admin and admin:password → "Invalid credentials"

### 10:18 — Git dump
- Dumped .git from portal → only auth.php (empty USERS array in HEAD)
- Git history (2 commits): initial implementation → "add gitbot user for automated validation pipeline"
- **Creds in git diff: `gitbot` / `G1tB0t_Acc3ss_2025!`**
- Commit by "Dev Team" <dev@variatype.htb>

### 10:19 — Testing creds
- Portal login: `gitbot:G1tB0t_Acc3ss_2025!` → 302 to /dashboard.php. Works!
- SSH: publickey only, password rejected
- Dashboard shows "Recent font builds from the variable font generator" — no files yet
- /files/ → 403 Forbidden
- Portal files: index.php, auth.php, dashboard.php, styles.css
- Dashboard is sparse — just shows generated fonts list

### 10:20 — Font generator testing
- Uploaded clean .designspace + real Roboto TTF → "Font generation failed during processing"
- Even valid-looking uploads fail — might need exact filename match or specific format
- OOB XXE in .designspace (entity in axis name attribute) → NO CALLBACK
- Python's fonttools XML parser (ElementTree) doesn't process DTD entities by default
- XXE is likely a dead end (strike 1)

**Pivot: The .designspace filename attribute could be a path traversal vector.**
**Or: fonttools processing might have a deserialization/code exec CVE.**

### 10:22 — Research + XXE attempts
- CVE-2023-45139: XXE in fonttools < 4.43.0 via XMLReader/SAX parser
- Tried XXE in axis name attribute → no callback (strike 1)
- Tried XXE in source familyname attribute → no callback (strike 2)
- Tried XXE in lib/dict/string text content → no callback
- Path traversal in source filename → same "failed during processing" error
- **Conclusion: XXE not working. Server likely runs fonttools >= 4.43.0 (patched)**
- **3 strikes on XXE. Moving on.**

### 10:25 — Upload analysis
- Filename traversal in upload headers accepted (no sanitization) but generation fails
- Non-.designspace files rejected: "must be a valid .designspace document"
- Tried path traversal in designspace source filename attr → same processing error
- Portal dashboard still shows "No generated fonts found" after all attempts
- Need to make a SUCCESSFUL generation to see what files appear on portal
- Font creation locally is proving difficult with fonttools API

**Key insight: Portal serves files from /files/ directory. If generator writes output 
there as a .php file, we get RCE. Need to understand the output path.**

### 10:28 — Font generation always fails
- Tried DejaVu Sans (valid system TTF) + matching designspace → still fails
- **3 strikes on font generation.** Every upload fails with same error.
- Maybe that's by design — the exploit might not require successful generation
- The uploaded file might still be written to disk even if processing fails

### 10:30 — Back to portal
- Git only contains auth.php — dashboard.php, index.php not in repo
- No LFI via query params on dashboard.php
- No PHP source disclosure
- Need to look harder at what the portal does with generated fonts

### 10:31 — Exhaustive font generator testing
- Tried DejaVu Sans with exact matching familyname/stylename → fails
- Tried absolute paths to system fonts → fails
- Tried format 5.0 designspace → fails
- Tried PHP webshell as .ttf → accepted but generation fails
- Non-.ttf/.otf masters rejected: "Only .ttf and .otf master fonts are supported"
- Portal dashboard never shows generated fonts
- No additional endpoints found on main site
- No SQLi on portal login (hardcoded array auth)
- SSH is key-only auth

**STOP. 3+ strikes on font generation. Something fundamental is different 
about how this works. I need to SURVEY what I'm missing, not keep trying variations.**

**What am I missing?**
- Maybe there's a queue/job system and results appear later?
- Maybe the output goes to a DIFFERENT subdomain?
- Maybe I need to check the PORTAL source more carefully
- Maybe the exploit is in the .designspace XML processing, not font generation

### 10:35 — More dead ends
- XInclude in designspace → no callback
- FamilyName path traversal → no output files
- Guessed filenames in portal /files/ → all 404
- No files in /uploads/, /output/, /generated/ on main site
- The font generator NEVER produces output (at least none visible to us)

**CRITICAL QUESTION: Am I even looking at the right vulnerability?**
- Maybe the font generator is a distraction
- Maybe the entry point is through the PORTAL, not the generator
- Maybe I need to enumerate MORE subdomains
- Maybe there's a way to register/create an account on the portal

### 10:38 — Complete re-survey  
- No additional subdomains (bigger wordlist confirmed only 'portal')
- No hidden endpoints on main site
- No parameter-based vulns on portal dashboard
- SSTI in designspace familyname → not reflected in error
- Command injection via upload filename → no OOB callback
- Command injection via designspace axis name → no OOB callback
- Small compatible font subset (80 glyphs) still fails processing
- Single master still fails processing
- **The font generation is ALWAYS broken on the server side**

**I'm stuck. Need to think about what I'm fundamentally missing.
Possible I need to look at this from a completely different angle.
Maybe the exploit isn't through the web at all — maybe the gitbot 
creds or the git repo contain more info I haven't found.**

### 10:42 — Found download.php and view.php!
- Background feroxbuster with bigger wordlist found: **download.php** and **view.php**
- view.php takes ?file= parameter, validates: must contain [something] (non-empty brackets)
- Path traversal (../) is ALLOWED in the filename!
- Any extension accepted (.ttf, .php, .txt)
- Empty brackets [] are rejected
- download.php always says "File parameter required" regardless of method
- view.php returns empty for files that don't exist (vs "Invalid file name" for bad format)

**Challenge:** Need actual files with brackets to exist on disk.
Variable font output format: FamilyName[axis].ttf
But font generation never succeeds so no files exist.

### 10:50 — CORRECTION: bracket bypass was false positive!
- All earlier "accepted" responses were CURL GLOBBING artifacts!
- curl without -g interprets [wght] as character range (w,g,h,t)
- With -g flag (correct), view.php rejects EVERYTHING as "Invalid file name"
- view.php accepts NO inputs at all — maybe it only works when files exist
- download.php always says "File parameter required" regardless of method
- UUIDs, hashes, numbers all rejected by view.php

**Need to find what format view.php actually accepts, or make files 
available so the dashboard shows them (and reveals the format).**

### 10:55 — BREAKTHROUGH: Font generation SUCCESS!
- Local build with fonttools varLib.build() revealed the issue: OS/2 table version 1 missing sCapHeight
- Fixed the font (set OS/2 version to 4, added sCapHeight/sxHeight)
- Uploaded fixed font → **SUCCESS!** "Your variable font is ready."
- Download link: `/download/vtusBYgZWgQ` (short base64-ish token)
- File identifiers are NOT filenames, they're SHORT TOKENS

### 10:56 — Font generation SUCCESS + LFI CONFIRMED
- Fixed font: OS/2 table version 1→4, added sCapHeight/sxHeight
- Uploaded → SUCCESS! Token: vtusBYgZWgQ, download: /download/vtusBYgZWgQ
- Portal dashboard now shows files as: variabype_<token>.ttf
- Portal params are **`f=`** NOT `file=` (wasted time with wrong param!)
- **LFI in download.php!** Uses `str_replace("../", "", $file)` — single pass
- Bypass: `....//` → after replace → `../`
- Traversal at depth 5: `....//....//....//....//....//etc/passwd` works!
- Read view.php + download.php source code
- User: **steve** (uid 1000, /home/steve, /bin/bash)
- Files dir: /var/www/portal.variatype.htb/public/files/

### Credentials
- gitbot:G1tB0t_Acc3ss_2025! (portal)

### 11:22 — Reading files via LFI
- Read /etc/passwd → user: **steve** (uid 1000)
- Read nginx configs: Flask at 127.0.0.1:5000, portal at /var/www/portal.variatype.htb/public
- **Read Flask app.py at /opt/variatype/app.py** — FULL SOURCE!
- Read view.php and download.php source

### Flask app.py key findings:
- Masters saved with ORIGINAL filename: `os.path.join(workdir, font.filename)` — **PATH TRAVERSAL!**
- designspace saved as hardcoded 'config.designspace'  
- Processing: `subprocess.run(['fonttools', 'varLib', 'config.designspace'], cwd=workdir)`
- Output goes to: `/var/www/portal.variatype.htb/public/files/variabype_<token>.ttf`
- Extension check: `font.filename.endswith(('.ttf', '.otf'))` — MUST end with .ttf/.otf

### download.php source:
- `str_replace("../", "", $file)` — single pass, bypassed with `....//`
- Reads from `/var/www/portal.variatype.htb/public/files/`
- Serves with readfile() (no PHP execution)

### 11:25 — Exploiting path traversal write
- Can write .ttf/.otf files to ARBITRARY paths via master filename traversal
- Wrote PHP webshell as cmd.php.ttf to portal public dir → file exists but nginx won't execute .php.ttf
- PHP path_info exploit (cgi.fix_pathinfo) → 404
- Can't write non-.ttf files (extension check)
- PHP 8.2

### Current blocker: can write arbitrary .ttf files anywhere, need them EXECUTED as PHP/code
