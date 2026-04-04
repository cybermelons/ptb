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

## Key New Finding
- Port 8000 (WCF) is **FILTERED** not closed — firewall rule exists, service IS running
- MSSQL login 18456 = auth processed but denied — not a network block, login restriction
- SQL03$ password not crackable (tried machine name, common defaults, empty — all PREAUTH_FAILED)
- SQL03$ created by admin (no ms-DS-CreatorSID), can't reset password
- Can write RBCD on FAKEPC$ (our machine) but that's circular — no useful target SPN

## Relay Results Round 2
- SMB→LDAP with --remove-mic: auth FAILED (LDAP signing enforced independently of MIC)
- SMB→MSSQL relay: "login from untrusted domain" — MSSQL detected cross-protocol relay
- SMB→SMB relay: signing required (expected)
- SMB→WinRM: not yet tested properly (target format issue)
- Wildcard DNS *.overwatch.htb → 10.10.14.80 WORKS (verified resolution)
- Still zero organic traffic from DC after 15+ min with wildcard active

## What's left to try
- SMB→WinRM relay with explicit target `http://10.129.244.81:5985`
- Kerberos relay (completely different from NTLM relay)
- Shadow credentials via RBCD chain
- Wait longer (sim bot might run on 15-30 min timer)
- The wildcard DNS + some coercion method we haven't tried

## Checkpoint — Cycle Assessment

### What I've tried (full list):
1. NTLM relay: SMB→LDAP, SMB→LDAPS, SMB→MSSQL, SMB→SMB (all failed)
2. RBCD: set on sqlsvc but no SPN, set on FAKEPC$ but circular
3. DNS: wildcard works, specific records work, zero callbacks in 15+ min
4. Kerberoast/AS-REP: no targets except guest
5. Password spray: sqlmgmt, employees — all failed
6. MSSQL: TCP denied (18456), named pipe denied, Windows auth denied
7. Named pipe 932cddcbdabde3f5: opens but .NET framing gets no response
8. SAMR password change on sqlmgmt: access denied
9. ADCS: not installed. Shadow creds: no write access. SPN-jack: denied.
10. coercer: PrinterBug works (SMB), WebDAV fails (no WebClient)

### What I have NOT tried:
- Kerberos relay (krbrelayx) — fundamentally different from NTLM relay
- Setting SPN on FAKEPC$ + DNS wildcard → force Kerberos auth to our controlled SPN
- Long wait (30+ min) for DNS callback simulation
- Checking if the overwatch.exe binary has a DIFFERENT pipe than 932cddcbdabde3f5
- UDP services (SQL Browser 1434, etc.)

## BREAKTHROUGH — Kerberos Relay Chain

### Setup (all successful):
1. Created FAKEPC$ machine account (FakeP@ss123!)
2. Set dNSHostName=FAKEPC.overwatch.htb on FAKEPC$
3. Added SPNs: cifs/FAKEPC.overwatch.htb, HOST/FAKEPC.overwatch.htb
4. Added DNS A record: FAKEPC.overwatch.htb → 10.10.14.80
5. Wildcard DNS *.overwatch.htb → 10.10.14.80
6. Kerberos TGS for cifs/FAKEPC.overwatch.htb: VERIFIED WORKING
7. PrinterBug coercion → DC authenticates with Kerberos to our SMB server
8. krbrelayx decrypts the Kerberos ticket with FAKEPC$'s NT hash

### Current blocker:
- krbrelayx in "unconstrained delegation abuse" mode needs forwarded TGT
- FAKEPC$ doesn't have unconstrained delegation (can't set it, need admin)
- Without TGT, can't relay to LDAP
- Error: "Delegate info not set, cannot extract ticket!"

### Next steps:
- Try krbrelayx WITHOUT --delegate-access (regular relay, not delegation abuse)
- The authenticated SMB session IS valid — krbrelayx just crashes on authdata extraction
- May need to modify krbrelayx to use the authenticated session differently
- Alternative: use the Kerberos service ticket + S4U2Proxy chain

## Decision Tree Test Results

### Test 1: Pipe 932cddcbdabde3f5 identity
- Computed SHA1/SHA256/MD5 of WCF endpoint URIs — NO MATCH
- Pipe is NOT the WCF named pipe endpoint
- RESULT: Hypothesis C (pipe = WCF) **weakened**

### Test 2: Raw text to pipe
- Sent \n, "help\n", HTTP GET, null bytes
- All timed out — pipe doesn't respond to simple text
- Pipe opens but needs specific binary protocol we haven't identified
- RESULT: **Inconclusive** — pipe exists but unknown protocol

### Test 3: Port 8000 with 30s timeout
- curl timed out after 30s — truly firewalled
- RESULT: Hypothesis B (port 8000 reachable) **ELIMINATED**

### Test 4: UDP services
- SQL Browser 1434: open|filtered, no response to probe
- SNMP 161: open|filtered, no response to public community
- DNS 53: open (known), NTP 123: open
- RESULT: No new attack surface from UDP

### Remaining hypotheses after elimination:
- A. MSSQL accessible somehow — HARD BLOCKED (18456 on all auth methods)
- B. Port 8000 reachable — ELIMINATED
- C. Pipe = useful service — INCONCLUSIVE (opens but no protocol match)
- D. Sim bot connects to DNS — UNTESTED at scale (need 10+ min wait)
- E. Undiscovered service — ELIMINATED (full TCP + UDP scanned)

### Classification per new CLAUDE.md:
- NTLM relay → HARD BLOCK (signing + channel binding, Server 2022)
- RBCD S4U → HARD BLOCK (no SPN on sqlsvc, can't set one)
- Kerberos relay → HARD BLOCK (can't set unconstrained delegation)
- Port 8000 direct → HARD BLOCK (firewalled)
- MSSQL remote → HARD BLOCK (login restriction)

### What's NOT hard-blocked:
1. Pipe 932cddcbdabde3f5 — opens, unknown protocol
2. DNS simulation callback — untested at proper duration
3. Some technique we haven't considered at all

## MSSQL Breakthrough

### Access via FAKEPC$ machine account
- FAKEPC$ can auth to MSSQL (BUILTIN\Users server principal)
- NOT sysadmin, no xp_cmdshell
- Can see: master, tempdb, msdb
- CANNOT access: overwatch DB, SecurityLogs DB (doesn't exist)
- No impersonation rights

### Linked Servers
- S200401\SQLEXPRESS → self (local, not configured for remote exec)  
- **SQL07** → linked server with `rpc,rpc out,data access` — SERVER DOES NOT EXIST
- SQL07 resolves to 10.10.14.80 (us!) via wildcard DNS

### Attack Vector
- Set up rogue MSSQL on our IP
- Trigger query via SQL07 linked server
- Rogue MSSQL responds with data/commands
- OR: capture credentials when DC connects to SQL07
