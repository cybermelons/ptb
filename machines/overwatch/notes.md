# Overwatch — 10.129.244.81

## FLAGS
- User: pending
- Root: pending

## Recon

- TTL=127 → Windows box
- nmap binary blocked (Operation not permitted), used bash /dev/tcp scan
- Open ports (common range): 53, 88, 135, 139, 389, 445, 464, 636, 3389, 5985
- This is a **Domain Controller** (88=Kerberos, 389=LDAP, 636=LDAPS, 53=DNS, 445=SMB)
- WinRM available (5985), RDP available (3389)
- Full port scan (10001-65535) not yet completed
- No HTTP on 80/443/8080/8443

## Enumeration

- Domain: OVERWATCH.HTB, DC: S200401.overwatch.htb
- Windows Server 2022 Build 20348, SMB signing required
- Guest account: AS-REP roastable, empty password, can list shares
- `software$` share contains `Monitoring/overwatch.exe` — .NET WCF service
- Creds from binary: `sqlsvc:TI0LKcfHzZw1Vv` (MSSQL connection string, localhost only)
- sqlsvc: SMB works, no WinRM, no MSSQL externally
- sqlmgmt: member of Remote Management Users (WinRM) — need creds
- Adam.Russell: Domain Admin

## overwatch.exe Analysis

.NET WCF service at `http://overwatch.htb:8000/MonitorService` (likely localhost only)
- `IMonitoringService` interface: `StartMonitoring()`, `StopMonitoring()`, `KillProcess(string)`
- **KillProcess**: PowerShell `Stop-Process -Name <input> -Force` → **COMMAND INJECTION**
- **LogEvent**: SQL concatenation → SQLi in type/detail params
- **CheckEdgeHistory**: reads Edge history SQLite, inserts URLs into MSSQL EventLog
  - SQLi via browsed URLs (URLs inserted unescaped)
- **StartProcessWatcher**: WMI `Win32_ProcessStartTrace`, logs process starts to MSSQL
- Connection: `Server=localhost;Database=SecurityLogs;User Id=sqlsvc;Password=TI0LKcfHzZw1Vv;`

## Attack Vectors
1. Need to reach WCF on port 8000 (not externally accessible) or find another way in
2. KillProcess → PowerShell injection → RCE
3. Need sqlmgmt creds for WinRM shell

## Failures / Dead Ends
- MSSQL (port 6520): rejects all external auth (sqlsvc, sa, sqlmgmt) — localhost only
- WinRM: sqlsvc rejected, sqlmgmt rejected (don't have password)
- Password reuse sqlsvc→sqlmgmt: failed
- Password spray sqlmgmt with common passwords: failed (badPwdCount=11)
- No Kerberoastable user accounts (only DC$ and krbtgt have SPNs)
- AS-REP roast: only Guest (empty pass), sqlmgmt requires preauth
- SMB C$/ADMIN$: denied for sqlsvc
- software$ share: read-only for sqlsvc
- Employee accounts: UAC 66080 = PASSWD_NOTREQD + NORMAL + DONT_EXPIRE — all enabled, NOT disabled
  - Empty password auth failed for all tested
- SCM service enumeration: access denied for sqlsvc
- RPC session enumeration: access denied
- No LAPS, no gMSA, no RBCD configured, no constrained delegation
- Port 8000 (WCF): not externally accessible

## ACL Analysis (bloodyAD)
- sqlsvc can WRITE `msDS-AllowedToActOnBehalfOfOtherIdentity` on **its own object** (RBCD on self — not useful alone)
- sqlsvc can CREATE_CHILD `dnsNode` in `overwatch.htb` and `_msdcs.overwatch.htb` DNS zones → **DNS write access**
- GenericAll on sqlmgmt: only Domain Admins and Enterprise Admins
- No writable attributes on sqlmgmt or S200401$ from sqlsvc
- MachineAccountQuota = 10 (can add machine accounts)

## PrinterBug Coercion Results
- PrinterBug (MS-RPRN) WORKS — DC connects back to us on 445
- Captured S200401$ NTLMv2 hash (saved in /tmp/ntlm_hashes.log)
- SMB→LDAP relay: FAILS — "client requested signing, relaying to LDAP will not work"
- SMB→LDAPS relay: FAILS — "socket ssl wrapping error: Connection reset by peer" (channel binding)
- Machine account passwords are not crackable (120-char random)
- Need HTTP-based coercion to bypass signing — WebDAV or DNS poisoning

## Machine Account Created
- FAKEPC$ / FakeP@ss123! — RID 7601
- Ready for RBCD delegation once we can relay successfully

## DNS Records Added (pointing to 10.10.14.80)
- portal, intranet, webmail, mail, helpdesk, monitor, dashboard, status — all .overwatch.htb
- wpad — blocked by GQBL, doesn't resolve
- All others resolve correctly via DC DNS

## Current Approach
- ntlmrelayx HTTP listener on port 80, relaying to LDAP
- Waiting for admin/service to browse to one of our poisoned hostnames
- No callbacks yet after 60 seconds — may need to trigger browsing somehow
- OR: need to find a way to coerce HTTP auth (WebDAV, WebClient)
- Patched ntlmrelayx (sys.stdin.read → sleep loop) at /usr/local/bin/ntlmrelayx_patched.py

## NTLM Relay Attempts (all failed)
- SMB→LDAP: signing blocks relay
- SMB→LDAPS: channel binding resets connection
- WebDAV PetitPotam: EFS access denied
- DNS poisoning (portal, intranet, webmail, etc.): no callbacks in 3+ minutes
- tcpdump shows ZERO traffic from DC to us (DC not browsing to our DNS records)
- The admin is NOT actively browsing internal hostnames we can poison

## Additional Findings
- SQL03$ computer account exists — UAC 4128 (PASSWD_NOTREQD), never logged in, no SPNs
- SQLServer2005SQLBrowserUser$S200401 group exists (empty)
- RBCD set on sqlsvc (bloodyAD) — "FAKEPC$ can impersonate on sqlsvc"
- But S4U2Proxy fails: sqlsvc has no SPN, KDC rejects unknown SPNs
- Can't set SPN on sqlsvc (insufficient access rights)
- Can't modify SQL03$ RBCD (no write access)
- sqlsvc has `scriptPath: WRITE` on itself (logon script — needs interactive logon to trigger)

## Ruled Out
1. ADCS — not installed, no CAs, no templates
2. Shadow credentials — no msDS-KeyCredentialLink write access
3. SPN-jacking sqlsvc — insufficient access to set servicePrincipalName
4. MSSQL named pipe (IPC$) — access denied  
5. MSSQL remote SQL auth — login failed (localhost-only restriction)
6. DNS callbacks — 5+ minutes, no traffic from DC to our DNS records
7. RBCD S4U2Proxy — works but sqlsvc has no SPN, KDC rejects

## Still Possible
1. MSSQL SQL injection via Edge URLs — the intended path likely involves Edge + MSSQL SQLi
2. SQL03$ — pre-staged computer account with PASSWD_NOTREQD, unexplored
3. Kerberos relay (vs NTLM relay) — different technique
4. The box may need us to WAIT for a simulated user to browse to our DNS record
5. There may be a scheduled task we can't see that periodically browses URLs
