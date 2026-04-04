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
