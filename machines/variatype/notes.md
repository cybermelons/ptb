# VariaType — 10.129.244.202

## Attack Chain Summary
1. Git dump on portal (.git exposed) → `gitbot:G1tB0t_Acc3ss_2025!`
2. Portal LFI (download.php `....//` bypass) → read Flask app.py source
3. Designspace format 5.0 `<variable-font filename="...">` → output path traversal
4. PHP polyglot font (PHP in name table + font binary) written as cmd.php → **RCE as www-data**
5. Steve's cron runs FontForge on uploaded fonts → Python CWD module hijack → **steve shell** (in progress, needs box reset)

## Key Learnings
- Input extension was checked (.ttf/.otf). **Output extension was NOT.**
- Think about what the code PRODUCES, not just what it accepts.
- fonttools varLib `main()` line 119: `filename = vf.filename if vf.filename is not None`
- The upload param was `f=` not `file=` — always fuzz parameter names
- download.php and view.php only found with BIGGER wordlist (not common.txt)
- PHP in a font binary works because PHP scans for `<?php` tags in any file
- Use platformID=1 (Mac/ASCII) for embedding text in font name tables (platformID=3 is UTF-16)
- Font generation kept failing because OS/2 table version was too old (needed sCapHeight)
- **Local build testing** revealed the issue immediately

## Dead Ends
1. XXE in .designspace (3 attempts, fonttools uses safe parser)
2. Extension bypass (null byte, RFC 5987, tab — all blocked by Python endswith)
3. SSTI via Flask |safe (doesn't re-evaluate Jinja2)
4. /etc/shadow readable by stat but not by content
5. curl globbing false positives (use -g flag!)
6. PHP path_info exploit (nginx try_files blocks it)

## Privesc: www-data → steve
- Steve runs `/home/steve/bin/process_client_submissions.sh` via cron
- Uses fontforge to process `variabype_*.ttf` from `/files/`
- fontforge's Python sys.path starts with `''` (CWD = /files/)
- Deploy `sitecustomize.py` or module hijack in /files/
- Steve's cron broke after hijack attempts — needs box reset

## Anti-Loop Postmortem
- Spent ~90 min on extension bypass before finding the OUTPUT path trick
- Should have read fonttools varLib source EARLIER (line 119 was the answer)
- The hint "think like a reverse engineer" meant: trace the code path, don't fuzz blindly
- Fuzz with LARGE wordlists early (view.php/download.php were hidden)
