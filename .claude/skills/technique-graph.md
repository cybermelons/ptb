# Technique Dependency Graph

When a path hits a hard block, use this graph to find alternative routes from your current capabilities. Each technique lists what you NEED (prerequisites) and what you GET (outputs). Match your current capabilities against prerequisites to find viable next steps.

## How To Use This

1. After a hard block: list what you currently control (the "I have" list)
2. Scan the prerequisites below — find techniques where you satisfy ALL requirements
3. Add matching techniques to `unexplored.jsonl`
4. Prioritize techniques that give you outputs you need for your goal

## Linux Techniques

### Initial Access

#### Web RCE (command injection, SSTI, deserialization, file upload)
- **Needs:** web app with exploitable endpoint, confirmed version/vuln
- **Gives:** shell as web service user
- **Hard block if:** app is patched, WAF blocks all payloads, no injectable parameter exists

#### SSH with credentials
- **Needs:** valid username + password/key, SSH accessible, PasswordAuthentication or matching key
- **Gives:** interactive shell as that user
- **Hard block if:** SSH not exposed, key-only and no key, account locked

#### SSH key injection (via file write)
- **Needs:** write to target user's `~/.ssh/authorized_keys`, SSH accessible
- **Gives:** interactive shell as that user

### Privilege Escalation (Linux)

#### sudo misconfiguration
- **Needs:** shell as user, `sudo -l` shows exploitable entry
- **Gives:** command execution as target user (often root)
- **Hard block if:** sudo requires password you don't have, no exploitable entries

#### SUID binary abuse
- **Needs:** SUID binary on GTFOBins (or custom exploitable binary)
- **Gives:** euid of binary owner (usually root). NOTE: euid only, not egid
- **Pivots to:** if you need real uid+gid, plant SSH key instead of using SUID shell

#### Cron/timer job hijack
- **Needs:** writable script/binary referenced by cron job, OR writable cron directory
- **Gives:** execution as the user who owns the cron job
- **Hard block if:** all cron scripts are root-owned and not writable

#### Kernel exploit
- **Needs:** known vulnerable kernel version, ability to compile/run exploit
- **Gives:** root shell
- **Hard block if:** kernel is patched, no compiler available, exploit crashes system (scope violation)
- **LAST RESORT** — exhaust all other options first

#### Capabilities abuse
- **Needs:** binary with dangerous capability (cap_setuid, cap_dac_override, cap_net_raw, etc.)
- **Gives:** varies by capability — often root-equivalent

#### Writable /etc/passwd or /etc/shadow
- **Needs:** write access to passwd/shadow
- **Gives:** root (add user or change root password hash)

### Credential Access

#### Config file harvesting
- **Needs:** file read as any user
- **Gives:** passwords, API keys, database creds
- **Look in:** `.env`, `*.conf`, `*.cfg`, `*.ini`, `wp-config.php`, `web.config`, `.git/config`, bash_history

#### Database credential extraction
- **Needs:** database access (direct or via SQLi)
- **Gives:** user credentials (often reused elsewhere)

#### Memory/process credential extraction
- **Needs:** root or same-user access, `/proc` readable
- **Gives:** credentials from running processes

## Windows / Active Directory Techniques

### Initial Access

#### Password spray
- **Needs:** username list, network access to auth service (SMB/LDAP/Kerberos)
- **Gives:** valid domain credential
- **Hard block if:** account lockout threshold is low and you've hit it, or fine-grained password policy blocks you

#### AS-REP roasting
- **Needs:** user account with DONT_REQUIRE_PREAUTH set
- **Gives:** offline-crackable hash for that user
- **Hard block if:** no accounts have the flag, or password is too complex to crack

#### Kerberoasting
- **Needs:** any valid domain credential, accounts with SPNs set
- **Gives:** offline-crackable TGS hash for SPN accounts
- **Hard block if:** no non-default SPNs exist, or service account passwords are strong/managed (gMSA)

#### NTLM relay (SMB source)
- **Needs:** coerced SMB auth from target, relay target without SMB signing
- **Gives:** authenticated session on relay target
- **Hard block if:** SMB signing required on relay target (ALL DCs require signing by default)

#### NTLM relay (HTTP source)
- **Needs:** coerced HTTP auth (WebDAV, WebClient service, browser), relay target without signing requirement
- **Gives:** authenticated session on relay target (LDAP/SMB/etc.)
- **Hard block if:** WebClient not running, no way to trigger HTTP auth, target requires signing/channel binding

#### Kerberos relay (krbrelayx)
- **Needs:** machine account with SPN you control, DNS pointing SPN hostname to you, coerced Kerberos auth
- **Gives:** decrypted Kerberos service ticket
- **DOES NOT give:** TGT (unless target has unconstrained delegation)
- **Pivots to:** use service ticket for S4U2Self, or exploit the authenticated session directly

### Lateral Movement / Privilege Escalation (AD)

#### RBCD (Resource-Based Constrained Delegation)
- **Needs:** write access to target's `msDS-AllowedToActOnBehalfOfOtherIdentity`, machine account you control, target must have SPN
- **Gives:** impersonated service ticket to target
- **Hard block if:** target has no SPN and you can't set one, or S4U2Proxy fails validation
- **Common trap:** setting RBCD on an account with no SPN — the S4U2Proxy step WILL fail at the KDC

#### Unconstrained delegation abuse
- **Needs:** machine with TRUSTED_FOR_DELEGATION flag, coerced auth from target
- **Gives:** target's TGT (full impersonation)
- **Hard block if:** no machine has unconstrained delegation, or you can't enable it (needs domain admin)
- **This is the Overwatch trap** — don't retry if the flag isn't set and you can't set it

#### Constrained delegation abuse (S4U2Self + S4U2Proxy)
- **Needs:** account with `msDS-AllowedToDelegateTo` set, or RBCD configured on target
- **Gives:** service ticket as impersonated user to the allowed service
- **Hard block if:** no delegation configured, target service doesn't have SPN

#### Shadow credentials
- **Needs:** write access to target's `msDS-KeyCredentialLink`
- **Gives:** certificate-based auth as target, then PKINIT for TGT
- **Hard block if:** no write access to the attribute, or AD CS not configured for PKINIT

#### ADCS abuse (ESC1-ESC8)
- **Needs:** AD CS installed, vulnerable certificate template
- **Gives:** certificate for impersonation, often domain admin
- **Hard block if:** AD CS not installed, or all templates patched

#### DCSync
- **Needs:** Replicating Directory Changes (+ Extended) rights — usually domain admin or equivalent
- **Gives:** all domain password hashes
- **Hard block if:** you don't have replication rights

#### SPN-jacking
- **Needs:** write access to target account's `servicePrincipalName`
- **Gives:** ability to Kerberoast that account (offline crack)
- **Hard block if:** no write access to SPN attribute

#### DNS poisoning + auth capture
- **Needs:** DNS write access (ADIDNS), target that resolves and authenticates to the poisoned name
- **Gives:** captured credential (NTLM hash or Kerberos ticket)
- **Hard block if:** no organic traffic to poisoned names, no way to trigger resolution

#### Pass-the-hash / pass-the-ticket
- **Needs:** NT hash or Kerberos ticket, target service accepts the auth type
- **Gives:** authenticated session as that principal
- **Hard block if:** credential is expired, target requires Kerberos and you only have NTLM (or vice versa)

### Credential Pivots

#### Machine account + DNS write → Kerberos interception
- **Needs:** controlled machine account with SPN, DNS write to point hostname to you, coercion method
- **Gives:** decrypted Kerberos service tickets
- **Does NOT give:** TGT, delegation, or LDAP relay (without additional primitives)
- **Pivots to:** extract PAC data, attempt S4U2Self from the captured session, use authenticated SMB session for share access

#### Coerced auth → relay chain
- **Needs:** coercion method (PrinterBug, PetitPotam, DFSCoerce), valid relay target
- **Gives:** authenticated session on relay target
- **Selection guide:**
  - SMB coercion (PrinterBug) → can only relay if target doesn't require SMB signing
  - HTTP coercion (WebDAV) → more flexible relay targets, but needs WebClient running

## Pivot Decision Framework

When you hit a hard block, work through this:

```
1. WHAT DO I HAVE?
   List: credentials, shells, write primitives, network position, controlled accounts

2. WHAT FAILED AND WHY?
   Name the specific structural reason (not "it didn't work")

3. WHAT TECHNIQUES MATCH MY CURRENT CAPABILITIES?
   Scan the graph above. For each match, check ALL prerequisites — not just the obvious ones.

4. WHAT'S THE SHORTEST PATH TO MY GOAL?
   Prefer techniques with fewer prerequisites and fewer untested assumptions.

5. ARE THERE CAPABILITIES I HAVEN'T FULLY ENUMERATED?
   Sometimes the pivot isn't a new technique — it's discovering you have access you didn't check.
   Re-run: what groups am I in? What ACLs do I have? What's writable?
```
