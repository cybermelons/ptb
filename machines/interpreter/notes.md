# Interpreter — 10.129.244.184

## FLAGS
- User: pending
- Root: pending

## Recon
- TTL=63 → Linux
- HTTP 80: Mirth Connect Administrator 4.4.0
- Mirth Connect = NextGen Healthcare integration engine (HL7/FHIR)
- **CVE-2023-43208**: pre-auth RCE via Java deserialization (affects < 4.4.1)
- JNLP confirms version 4.4.0
- Waiting for nmap results for full port list

## Foothold: mirth user via CVE-2023-43208
- Pre-auth RCE via XStream deserialization on POST /api/users
- Shell as mirth (uid=103) — service account, not a real user
- User sedric (uid=1000) has the flag, home is locked

## Survey Results
- Linux, hostname interpreter
- MySQL 3306 (localhost), port 54321 unknown, port 6661 (Mirth internal)
- No sudo binary, no useful SUID
- No cron jobs of interest
- SSH on 22

## Mirth Config (mirth.properties)
- DB: mirthdb:MirthPass123! → mysql mc_bdd_prod
- Keystore: storepass=5GbU5HGTOOgE, keypass=tAuJfQeXdnPw
- PERSON table: sedric (ID=2), hashed password in PERSON_PASSWORD
- Password hash: u/+LBBOUnadiyFBsMOoIDPLbUR0rk59kEkPU17itdrVWA/kLMt3w+w== (PBKDF2?)

## Credential Cross-Check (per methodology)
- SSH sedric: MirthPass123!, 5GbU5HGTOOgE, tAuJfQeXdnPw, admin, mirth, sedric → ALL FAILED
- SSH root: same → ALL FAILED
- Mirth API: all return FAIL for login
- su sedric from mirth shell: MirthPass123! → auth failure

## TODO
- Check port 54321 (what service?)
- Check Mirth channels for stored credentials
- Check CHANNEL table for JS code that might contain creds
- Look for sedric's SSH key or other files

## notif.py Service (port 54321)
- `/usr/local/bin/notif.py` — Python, runs as ROOT via systemd (notif.service)
- Owned by root:sedric (rwxr-x---) — mirth can't read, sedric can
- Listens on 127.0.0.1:54321, receives XML patient data from Mirth channel
- Mirth channel: TCP 6661 (HL7/MLLP) → transform → POST to /addPatient
- Box name "Interpreter" = this Python service likely has code injection
- Testing injection via curl but reverse shell output mangling makes it hard
- NEED: write a proper on-target test script, or use the Mirth channel to send data

## notif.py Injection Analysis

### Working request format:
- POST /addPatient with XML, DOB must be DD/MM/YYYY or MM/DD/YYYY
- Response: "Patient {fn} {ln} ({gender}), {age} years old, received from {sender} at {ts}"

### Input validation:
- Parentheses `()` → [INVALID_INPUT] (blocked)
- `{{expr}}` → renders as `{expr}` literally (NOT Jinja2)
- Digits in braces `{{7*7}}` → [INVALID_INPUT]  
- Single quotes in braces → [INVALID_INPUT]
- The app uses Python str.format() or f-strings, NOT Jinja2
- Box name "Interpreter" = likely Python eval/exec somewhere with filters

### What's NOT blocked:
- Alphanumeric names
- Underscores and dots ({{self.__class__}} renders as {self.__class__})
- The response interpolates firstname, lastname, gender, sender_app, timestamp directly

### Next: find the actual injection point
- Maybe it's not SSTI but Python format string vulnerability
- Try {0}, {1.__class__} etc for str.format() exploitation
- Or the service might eval() a specific field with filtered chars
