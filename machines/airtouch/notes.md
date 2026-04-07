# AirTouch — Worklog

## 01:15 — Recon
- Target: 10.129.244.98
- nmap TCP full: only port 22 (SSH) open
- nmap UDP top 50: port 161 (SNMP) open
- SSH: OpenSSH 8.2p1 Ubuntu 4ubuntu0.11

## 01:18 — SNMP Enumeration
- `snmpwalk -v2c -c public` → readable with default community string
- sysDescr leaks password: `RxBlZhLmOkacNWScmZ6D` ("default consultant password")
- sysContact: admin@AirTouch.htb
- sysName: Consultant

## 01:19 — SSH as consultant
- cred-001 works: `consultant:RxBlZhLmOkacNWScmZ6D`
- uid=1000(consultant), hostname=AirTouch-Consultant
- **sudo ALL NOPASSWD** — full root on this container
- Ubuntu 20.04, kernel 5.4.0-216
- No flags here — this is a stepping stone

## 01:20 — WiFi Environment
- 7 wireless interfaces (wlan0-wlan6)
- eaphammer installed in /root/
- aircrack-ng suite available

### Network Diagram (from ~/diagram-net.png):
- **Consultant VLAN** (172.20.1.0/24) — where we are
- **Tablets VLAN** (192.168.3.0/24) — SSID: AirTouch-Internet (WPA2-PSK)
- **Corp VLAN** (10.10.10.0/24) — SSID: AirTouch-Office (WPA2-Enterprise 802.1X)
- NAT forwards :22 and :161 to 172.20.1.2

### WiFi Scan Results:
| SSID | BSSID | Ch | Auth | Target? |
|------|-------|-----|------|---------|
| AirTouch-Internet | f0:9f:c2:a3:f1:a7 | 6 | WPA2-PSK | YES |
| AirTouch-Office | ac:8b:a9:f3:a1:13 | 44 (5GHz) | WPA2-Enterprise | YES |
| AirTouch-Office | ac:8b:a9:aa:3f:d2 | 44 (5GHz) | WPA2-Enterprise | YES (2nd AP) |

## Plan
1. Capture WPA2 handshake on AirTouch-Internet → crack PSK → Tablets VLAN
2. Evil twin AirTouch-Office with eaphammer → capture 802.1X creds → Corp VLAN
3. Enumerate internal hosts on each VLAN

## 01:41 — Checkpoint

### Model I'm operating under:
Evil twin to capture 802.1X creds → access Corp VLAN. This is HARD BLOCKED because client validates CA fingerprint, not just subject.

### Strongest negative result to re-examine:
None of the negative results seem wrong. The CA validation is real.

### Unverified assumptions:
1. I assume the PSK router login can't be brute-forced — haven't tried a wordlist
2. I assume I can't reach Corp VLAN (10.10.10.0/24) — haven't tested routing from wlan0 or eth0
3. I haven't checked gateway 172.20.1.1 for services
4. I haven't tried connecting to AirTouch-Office with real creds via wpa_supplicant (TLS handshake works without CA pinning from our side!)
5. I haven't investigated the neighbor WiFi networks

### Pivot options:
1. **Direct PEAP auth** — use wpa_supplicant to auth to real AirTouch-Office with candidate creds (TLS works from our end)
2. **Gateway enum** — check 172.20.1.1 for services
3. **Web brute force** — wordlist attack on 192.168.3.1 login
4. **Neighbor WiFi** — crack and explore neighbor networks (part of lab?)

### What was tested since checkpoint:
- Gateway 172.20.1.1: only SSH, no other services ✗
- Corp VLAN unreachable from consultant/tablets VLANs ✗
- PEAP auth to real AP with admin:RxBlZhLmOkacNWScmZ6D → error 691 (wrong creds) ✗
- Web login: tried admin@AirTouch.htb, manager, tablet, root, AirTouch → all failed ✗
- SNMP alternate community strings → all timed out ✗
- Evil twin cert matching: client validates CA hash, not just subject (HARD BLOCK) ✗
- 3 corp clients found: C8:8A:9A:6F:F9:D2, 28:6C:07:12:EE:A1, 28:6C:07:12:EE:F3
- All clients validate CA cert → evil twin approach dead
- Real RADIUS CA: CN=AirTouch CA, hash=222a7dd4...
- Real RADIUS server: CN=AirTouch CA (server cert), hash=ef39f3ff...
- Box crashed at ~01:46, SSH refused

## 01:46 — Box Down
- Box crashed during multi-interface WiFi attacks
- SSH port 22 shows closed, host responds to ping
- Waiting for reboot...

## Next Steps When Box Returns:
1. **Try neighbor WiFi networks** — capture PMKID or handshakes from vodafoneFB6N, MOVISTAR_FG68, WIFI-JOHN, MiFibra-24-D4VY
2. **Brute force web login** with a wordlist (hydra or custom script)
3. **Try more PEAP creds** — consultant:challenge, consultant:RxBlZhLmOkacNWScmZ6D on the real AP
4. **Check dnsmasq 2.90 CVEs** on the PSK router
