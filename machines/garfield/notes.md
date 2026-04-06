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

## Dead Ends Summary
- Password spray: thousands of candidates, all failed
- Hash cracking: rockyou, 10M, 412K themed, rules — uncrackable
- NTLM relay: signing blocks LDAP, channel binding blocks LDAPS
- Reverse shell via bat: AV/AMSI blocks PowerShell
- RODC01 (192.168.100.2): not reachable from attacker
- Logon script simulation: worked ONCE on first instance, never again

## Open Questions
- Why did l.wilson's hash appear on the FIRST instance but never again?
- Is there a way to TRIGGER l.wilson's logon rather than waiting?
- Are there attack paths we haven't considered? (ADIDNS, GPO abuse, other writable attributes?)
- What is the INTENDED entry point the box maker designed?

## Current Capabilities
- j.arbuckle creds (domain user, IT Support)
- WriteProp(scriptPath) on all users in CN=Users
- SYSVOL scripts/ write access
- Machine account FAKEPC$ with known password
- PetitPotam coercion (DC01$ auths to us, but can't relay)
