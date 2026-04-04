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

## Current Attack Plan
- DNS poisoning: sqlsvc can write DNS records
- Possible: create DNS record to redirect traffic, MITM something
- Possible: RBCD on self + add machine account = impersonate users TO sqlsvc? (need to think through)
- Need to figure out how DNS write + machine account + RBCD chains together
- Or: DNS redirect to capture NTLMv2 hashes from services connecting somewhere
