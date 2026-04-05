# AirTouch — 10.129.18.57

## 02:09 — Recon
- nmap TCP: only port 22 (OpenSSH 8.2p1 Ubuntu)
- nmap UDP: port 161 (SNMP) open
- SNMP walk (community: public) → sysDescr leaks password: `RxBlZhLmOkacNWScmZ6D` ("default consultant password")
- Contact: admin@AirTouch.htb, hostname: Consultant

## 02:11 — Initial Access
- `consultant:RxBlZhLmOkacNWScmZ6D` → SSH works
- Root on Docker container `AirTouch-Consultant` (172.20.1.2/24)
- sudo NOPASSWD: ALL
- No flags on this container

## 02:12 — Container Survey
- Docker container, gateway 172.20.1.1 (only SSH, firewalled from container)
- 7 wireless interfaces (wlan0-wlan6), all support 2.4GHz + 5GHz
- eaphammer 1.14.0 installed in /root/eaphammer
- hostapd binary is hostapd-mana + hostapd-wpe patched

## 02:13 — WiFi Scan
| SSID | Auth | Channel | BSSID | Notes |
|------|------|---------|-------|-------|
| AirTouch-Office | WPA2-Enterprise 802.1X | 44 (5GHz) | ac:8b:a9:aa:3f:d2, ac:8b:a9:f3:a1:13 | TARGET — 2 active clients |
| AirTouch-Internet | WPA-PSK CCMP/TKIP | 6 | f0:9f:c2:a3:f1:a7 | No clients observed |
| vodafoneFB6N | WPA-PSK TKIP | 1 | de:e2:00:78:aa:6e | Neighbor |
| MOVISTAR_FG68 | WPA-PSK CCMP/TKIP | 3 | c6:87:ca:23:10:45 | Neighbor |
| WIFI-JOHN | WPA-PSK CCMP/TKIP | 6 | 2e:7a:16:9b:4d:fc | Neighbor |
| MiFibra-24-D4VY | WPA2-PSK CCMP | 9 | 72:2a:e9:ba:38:5a | Neighbor |

## 02:15 — Evil Twin Attempt 1 (GTC Downgrade)
- Launched eaphammer evil twin on AirTouch-Office, wlan1, ch44, hw-mode a
- Two clients connected: 28:6c:07:12:ee:a1 and c8:8a:9a:6f:f9:d2
- Both used PEAP (method 25)
- Both REJECTED our cert: `tlsv1 alert unknown ca`
- TLS tunnel never formed → no credential capture
- **Key insight**: cert validation is the blocker, not the EAP negotiation

## 02:28 — Current State
- hostapd-eaphammer binary has mana+WPE patches (confirmed via strings)
- WPE should log MSCHAPv2 challenge/response even on cert rejection
- Need to check: does eaphammer config enable WPE logging? Does the hostapd log contain captured hashes?
- Also unexplored: connecting TO AirTouch-Internet with wpa_supplicant

## Dead Ends
- SSH to Docker host 172.20.1.1 — connection timed out (firewalled)
- No flags on consultant container
- AirTouch-Internet has zero clients — no handshake capture possible

## 02:42 — AirTouch-Internet PSK Cracked
- hcxdumptool captured 2 WPA handshakes from AirTouch-Internet
- aircrack-ng + rockyou: **PSK = `challenge`**
- Next: connect to AirTouch-Internet with wpa_supplicant, enumerate new network segment

## 02:50 — Checkpoint: Strategic Re-evaluation

### Current Model:
- AirTouch-Internet gateway (192.168.3.1) has a minimal web app (login.php + uploads/)
- Title: "PSK Router Login" — this configures the PSK router
- Known creds don't work on login or SSH
- SQLi bypass attempts failed

### What am I missing?
1. The login could be brute-forced with a targeted wordlist
2. I haven't tried the **AirTouch-Office** enterprise network path properly yet
3. The evil twin cert rejection was a HARD block for self-signed certs — but what if the CA cert is obtainable from somewhere?
4. hcxdumptool also captured frames from **AccessLink** (new SSID!) and **AirTouch-Office** — I should investigate these

### Key observation from hcxdumptool output:
- Captured a probe/association from BSSID c8:8a:9a:6f:f9:d2 for "AccessLink" — this is a NEW SSID not seen in original scan!
- Same capture showed AirTouch-Office association from same BSSID

### Next priorities:
1. Investigate "AccessLink" SSID — new discovery from hcxdumptool
2. Try password brute-force on login.php with common router admin passwords
3. Check if DNS on 192.168.3.1 resolves any internal hostnames

## 02:57 — Checkpoint: Full Strategic Pivot

### Current capabilities:
1. Root on Docker container AirTouch-Consultant (172.20.1.2)
2. Connected to AirTouch-Internet WiFi (192.168.3.84/24)
3. 7 wireless interfaces (wlan0-wlan6), eaphammer installed
4. Creds: consultant:RxBlZhLmOkacNWScmZ6D (SSH), AirTouch-Internet PSK: challenge

### Hard blocks:
- Evil twin with self-signed cert → clients validate CA (tlsv1 alert unknown ca)
- WPE log capture → requires TLS tunnel to form first (phase 1 blocks phase 2)
- Web login brute force → not in rockyou (59K), not common defaults
- SSH to Docker host → firewalled from container
- SSH to router 192.168.3.1 → consultant creds rejected

### What I haven't tried:
1. **Deauth clients from AirTouch-Office and capture a WPA2-Enterprise EAP exchange (not evil twin)**
   - Capture the FULL EAP exchange between client and real AP
   - Use airodump to capture the 4-way handshake / EAP frames
   - Even though it's enterprise, there may be crackable MSCHAPv2 hashes in the air
2. **Connect to AirTouch-Office as a client** with known creds?
   - wpa_supplicant with PEAP-MSCHAPv2 using consultant creds
3. **Crack neighbor WiFi PSKs** — vodafoneFB6N, MOVISTAR_FG68, WIFI-JOHN, MiFibra-24-D4VY
   - These are out of scope (not AirTouch) but hcxdumptool may have captured their handshakes too
4. **SNMP on 192.168.3.1** — is SNMP available on the router?
5. **UDP scan on 192.168.3.1** — may have more services

### Most promising path:
Try connecting to AirTouch-Office using wpa_supplicant with PEAP-MSCHAPv2 using consultant creds.
If enterprise auth succeeds, we get onto the office network which likely has the flags.

## 03:15 — Checkpoint: Deep Stuck Analysis

### Verified architecture from diagram:
- Consultant VLAN: 172.20.1.0/24 (Docker container, SSH+SNMP NAT'd)
- Tablets VLAN: 192.168.3.0/24 (AirTouch-Internet WiFi, PSK=challenge)
- Corp VLAN: 10.10.10.0/24 (AirTouch-Office WiFi, 802.1X)
- Corp computer 10.10.10.2 reachable via ICMP but ALL TCP filtered from Tablets VLAN
- Router 192.168.3.1: SSH(22), DNS(53), HTTP(80) — web login resists all brute force

### What am I fundamentally missing?

The router login is the bottleneck. I've tried:
- 59K rockyou passwords with admin
- Multiple usernames (admin, root, manager, tablet, airtouch, consultant, etc)
- SQLi bypass
- Source disclosure, .git, LFI attempts
- SSH with various creds

Things I haven't tried on the router:
1. **Apache version 2.4.41 — known CVEs?** This is old (2019).
2. **PHP vulnerabilities?** Maybe there's a PHP deserialization or session issue.
3. **Host header injection?** Maybe login.php behaves differently with certain headers.
4. **Virtual hosts?** Maybe there's a different site at a different hostname.
5. **The photo image** — I viewed it but it's a low-res hand-drawn copy of the diagram.

### Apache 2.4.41 CVEs to check:
- CVE-2021-41773 / CVE-2021-42013 — path traversal / RCE (Apache 2.4.49/2.4.50)
  - NOT applicable to 2.4.41
- CVE-2019-0211 — Apache priv esc (2.4.17-2.4.38) — NOT applicable to 2.4.41
- CVE-2021-40438 — mod_proxy SSRF — need mod_proxy
- Actually 2.4.41 is from late 2019, might have various issues

### New idea: check virtual hosts

## 03:32 — USER FLAG + Major Pivot
- **user.txt**: `b9391ac4dbdac3d098328e099c53b7a2` (in /root on AirTouch-AP-PSK)
- Attack chain: SNMP creds -> SSH container -> WiFi PSK crack -> WiFi traffic decrypt -> session hijack -> cookie IDOR -> file upload RCE -> su user -> sudo root
- Found send_certs.sh: `remote:xGgWEwqUpfoOVsLeROeG` for SSH to 10.10.10.1 (AirTouch-Office)
- Found CA cert backup + server cert/key for enterprise WiFi
- Next: SSH to 10.10.10.1 as remote, find root.txt

## 03:54 — ROOT FLAG CAPTURED

### Flags:
- **user.txt**: `b9391ac4dbdac3d098328e099c53b7a2` (AirTouch-AP-PSK /root/user.txt)
- **root.txt**: `97fb21a5c6dbb7efd11b1c85ea068b89` (AirTouch-AP-MGT /root/root.txt)

### Full Attack Chain:
1. SNMP info leak → consultant:RxBlZhLmOkacNWScmZ6D (SSH creds)
2. SSH to Docker container → root via sudo NOPASSWD
3. WiFi recon → 7 interfaces, AirTouch-Internet (PSK), AirTouch-Office (802.1X)
4. hcxdumptool → captured WPA handshake for AirTouch-Internet
5. aircrack-ng → cracked PSK: "challenge"
6. Connected to AirTouch-Internet → Tablets VLAN 192.168.3.0/24
7. Network diagram found in ~/diagram-net.png → revealed 3-VLAN architecture
8. Router at 192.168.3.1 → web panel (login.php) with uncrackable password
9. Monitor mode WiFi decrypt → captured tablet's HTTP session cookie
10. Cookie IDOR → UserRole=admin → file upload form revealed
11. Uploaded PHP webshell → RCE as www-data on router
12. login.php source → hardcoded creds + commented-out user:JunDRDZKHDnpkpDDvay
13. su user → sudo NOPASSWD ALL → root on router → **user.txt**
14. /root/send_certs.sh → remote:xGgWEwqUpfoOVsLeROeG + CA/server certs for AirTouch-Office
15. Evil twin with real certs → captured MSCHAPv2: r4ulcl:laboratory (cracked with darkc0de)
16. Connected to AirTouch-Office as AirTouch\r4ulcl → Corp VLAN 10.10.10.0/24
17. SSH to 10.10.10.1 as remote → read /etc/hostapd/hostapd_wpe.eap_user
18. Found admin:xMJpzXt4D9ouMuL3JJsMriF7KZozm7
19. SSH as admin → sudo NOPASSWD ALL → **root.txt**
