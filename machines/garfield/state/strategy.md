# Strategy (auto-generated, iteration 200)

## Current Position
Phase: exploit
Creds: j.arbuckle@ (password), l.wilson_adm@ (password), RODC01$@ (password), RODC01$@ (password), krbtgt_8245@ (password)
Priority: use creds to gain shell or escalate.

## Credentials (EXACT)
- j.arbuckle:Th1sD4mnC4t!@1978 (password via HTB provided creds)
- l.wilson_adm:P@ssw0rd2026! (password via ForceChangePassword via script)
- RODC01$:N3wR0dcP@ss! (password via ForceChangePassword by l.wilso)
- RODC01$:NewRodcPass123! (password via ForceChangePassword via l.wils)
- krbtgt_8245:KrbtgtPass123! (password via ForceChangePassword via RODC01)
- RODC01$:N3wR0dcP@ss! (password via rpcclient setuserinfo2 - updat)
- l.wilson_adm:P@ssw0rd2026! (password via Confirmed working on fresh ins)

## Confirmed Facts (49)
- Initial recon on Garfield
- Anonymous/null access reveals domain users
- More themed Garfield usernames exist
- j.arbuckle:Th1sD4mnC4t!@1978 are valid domain creds
- Bloodhound reveals ACL abuse path from j.arbuckle
- j.arbuckle can write to SYSVOL scripts directory
- PetitPotam coercion captures useful NTLM hash
- Raw ACL audit reveals paths Bloodhound missed
- Box IP changed from 10.129.16.228 to 10.129.17.44
- Wildcard DNS via krbrelayx dnstool.py resolves correctly
- DNS via nsupdate GSS-TSIG works where dnstool.py LDAP records didn't
- FAKEPC$ with dNSHostName + SPNs + DNS = Kerberos auth capture target
- GPO reveals l.wilson has SeBatchLogonRight — scheduled task runs as l.wilson
- DC01 has additional services beyond initial scan
- A full TCP port scan of 10.129.17.178 will reveal services not found in previous
- scriptPath change triggers logon task execution
- PowerShell Set-ADAccountPassword in bat resets l.wilson_adm password
- l.wilson_adm (Tier 1 group) has ForceChangePassword extended right on RODC01$ co
- RODC chain: l.wilson_adm -> RODC01$ -> krbtgt_8245
- RBCD on RODC01$ via WriteAccountRestrictions
- Gate overlap threshold too aggressive at 60%
- Disabled keyword overlap gate - too aggressive for privesc phase
- j.arbuckle:Th1sD4mnC4t!@1978 credentials are valid on 10.129.17.158 and can writ
- j.arbuckle credentials and SYSVOL write access persist on fresh DC instance 10.1
- scriptPath chain replay on .158
- RBCD+S4U+altservice chain to Administrator ticket for DC01
- S4U ticket for cifs/RODC01$ (no altservice)
- l.wilson_adm (Tier 1 admin) can execute remote commands via WinRM on 10.129.17.1
- l.wilson_adm can execute arbitrary commands via WinRM on DC01 (10.129.17.158) an
- keylistattack returns empty because PRG has zero members
- RODC01 at 192.168.100.2 is reachable via ping from DC01 using l.wilson_adm WinRM
- Bat exfil with temp file + SMB copy
- Bat writes to l.wilson desktop
- l.wilson_adm cant read ANY l.wilson files due to WinRM restrict

## Dead Ends — DO NOT RETRY (20)
- SMB null or LDAP anonymous reveals shares/users — DC restricts both null SMB share listing and anony
- j.arbuckle can execute commands via smbexec/psexec/atexec/wm — All return rpc_s_access_denied or 'share not writa
- j.arbuckle still has read access to C$/ADMIN$ on new IP 10.1 — No READ/WRITE on C$ or ADMIN$. Only IPC$, NETLOGON
- LAPS/gMSA/ADCS/password-in-description available — No LAPS deployed, no gMSA accounts, no ADCS, descr
- RODC01 (192.168.100.2) is reachable from attacker — 100% packet loss. Internal-only network, not route
- IT Support WriteProp on bf9679a8 controls group membership — bf9679a8 = scriptPath, NOT member. The ACE gives W
- Relay DC01$ SMB auth to LDAP for RBCD — SMB client requested signing - LDAP relay fails. E
- Relay DC01$ to LDAPS bypasses signing issue — LDAPS channel binding enforced: 'socket ssl wrappi
- Logon simulation processes scriptPath on fresh instance (3rd — 20 minutes polling, zero captures from responder, 
- Modify RODC01 DNS to redirect replication traffic — insufficientAccessRights. RODC01 DNS record owned 
- noPac CVE-2021-42278/42287 sAMAccountName spoofing — ERROR_INVALID_ACCOUNT_NAME (0x523) — DC rejects sA
- PrintNightmare CVE-2021-1675 with j.arbuckle creds — 0x8001011b error — failed to enumerate pDriverPath
- FAKEPC$ machine account has different access than j.arbuckle — FAKEPC$ has identical access to j.arbuckle. No Win
- Adding printer via RPC triggers printerDetect.bat — All printer operations return ACCESS_DENIED or 

## Failed Attempts
- Garfield reachable via machines_us-4 VPN (1x)
- j.arbuckle or l.wilson has a weak/themed password (1x)
- Additional DNS records reveal more hostnames/services (1x)
- ntlmrelayx can relay DC01$ to LDAP for RBCD (1x)
- printerDetect.bat is a GPO logon script that triggers on use (1x)
- l.wilson password follows j.arbuckle pattern with character/ (1x)
- l.wilson NTLMv2 hash crackable with rockyou/rules/themed/dar (1x)
- Reverse shell via scriptPath bat works (1x)
- Bat redirect output to UNC SMB share works (1x)
- l.wilson scriptPath logon script still fires after initial c (1x)
- l.wilson logon simulation fires on fresh box instance within (1x)
- Logon script simulation fires on fresh box (1x)
- ADIDNS records with j.arbuckle ownership resolve in DNS (1x)
- Wildcard DNS + ntlmrelayx captures auth from DC processes (1x)
- password-spray-l.wilson-garfield-theme (1x)
- full-tcp-scan-current-ip (1x)
- full-tcp-scan-178 (1x)
- Standard golden ticket with RODC krbtgt fails - need RODC-aw (1x

## Open Questions
1. Get ssh_accessible to unlock ssh_with_creds? (gives: interactive_shell)
2. Get accounts_with_spns to unlock kerberoasting? (gives: offline_crackable_tgs_hash)
3. Get relay_target_without_smb_signing to unlock ntlm_relay_smb? (gives: authenticated_session_on_relay_target)
4. Get traffic_to_poisoned_name to unlock dns_poisoning? (gives: captured_credential)
5. Retry or abandon: DNS zone transfer or RID cycling reveals additiona?
6. Retry or abandon: DC01 cannot connect back to us on port 445 via raw?
7. Retry or abandon: ntlmrelayx can relay DC01$ PetitPotam to LDAP for ?
8. Retry or abandon: ADIDNS records created via LDAP resolve in DNS?
9. Retry or abandon: ADIDNS records via dnstool.py resolve on fresh ins?

## Available Techniques (by readiness)
- password_spray: 100% (missing: ready) → valid_domain_credential
- ssh_with_creds: 66% (missing: ssh_accessible) → interactive_shell
- kerberoasting: 50% (missing: accounts_with_spns) → offline_crackable_tgs_hash
- ntlm_relay_smb: 50% (missing: relay_target_without_smb_signing) → authenticated_session_on_relay_target
- dns_poisoning: 50% (missing: traffic_to_poisoned_name) → captured_credential

## Operator Notes (AUTHORITATIVE)
- TWO ROOT PATHS IDENTIFIED: (1) Constrained delegation: l.wilson_adm GenericAll on RODC01$ → write msDS-AllowedToDelegateTo=cifs/DC01.garfield.htb → set T2A4D flag if needed → S4U2Self as Administrator → S4U2Proxy to DC01 → psexec. Risk: SeEnableDelegationPrivilege may block the write. Test with bloodyAD set object RODC01$ msDS-AllowedToDelegateTo. (2) PRG chain: j.arbuckle WriteProp on RODC PRG member attr → add l.wilson to Allowed RODC PRG → trigger bat logon (interactive=TGT) → RODC caches l.wilson creds → keylistattack with RODC01$ creds returns hashes. Path 1 is faster (no timing dependency). Try path 1 first, fall back to path 2.
- PATH 1 (constrained delegation) DEAD — verified against state: msDS-AllowedToDelegateTo write returns insufficientAccessRights (tried 2x), userAccountControl blocked by AD PARTIAL_SECRETS_ACCOUNT enforcement, SeEnableDelegationPrivilege required even with GenericAll. Do not retry any delegation attribute writes on RODC01$.
- PATH 2 (PRG chain) NEEDS RE-TEST — j.arbuckle WriteProp(member) on PRG is confirmed in ACL scan, but all add-member attempts were hard-blocked. Possible soft failure misclassified as hard. Re-test with exact syntax: bloodyAD or ldapmodify adding l.wilson DN to PRG member attribute using j.arbuckle creds. If PRG add works → trigger bat logon → RODC caches l.wilson → keylistattack with RODC01$ creds.
- PRG CHAIN DEAD — verified statically. (1) WriteProp(member) on PRG was misclassified ACE, actual is WriteProp(scriptPath). 4 principals tested, all access denied. (2) keylistattack independently broken — AES keys from ForceChangePassword produce BAD_INTEGRITY. Both pillars of PRG chain are hard-blocked. Need entirely new root approach.
