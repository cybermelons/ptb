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

### 10:42 — Rethinking
