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

### 10:22 — Research fonttools CVEs + path traversal
