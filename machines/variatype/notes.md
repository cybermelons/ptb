# VariaType — 10.129.244.202

## Attack Chain Summary
1. Git dump on portal → gitbot creds
2. Portal LFI (download.php ....// bypass) → read Flask source
3. Designspace format 5.0 variable-font filename → output path traversal
4. PHP polyglot font written as cmd.php → RCE as www-data
5. TODO: escalate to steve → root

## Key Learning
Input extension was checked (.ttf/.otf). Output extension was NOT.
Think about what the code PRODUCES, not just what it accepts.

## Privesc: www-data → steve (in progress)
- Steve runs /home/steve/bin/process_client_submissions.sh via cron
- Script uses fontforge (C binary with Python) to process font files
- fontforge -lang=py -c "import fontforge; font = fontforge.open('variabype_XXX.ttf')"
- CWD appears to be /var/www/portal.variatype.htb/public/files/
- Python sys.path starts with '' (CWD) — hijack opportunity
- Attempted: fontforge.py hijack (didn't work — C module pre-loaded)
- Attempted: sitecustomize.py (loaded too early, before CWD in sys.path)
- Steve's cron may have stopped running (possibly broken by our hijack attempts)
- Need box reset or alternative approach

## Files written to portal
- cmd.php — webshell (binary font + PHP)
- /files/fontforge.py.ttf, sitecustomize.py.ttf — hijack payloads
