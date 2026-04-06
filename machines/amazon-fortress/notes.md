# Amazon Fortress — Worklog

## Target: 10.13.37.15
## Started: 2026-04-06

---

## Recon Phase

### Initial setup
- Scope updated to 10.13.37.15
- Workspace created: machines/amazon-fortress/{scans,exploits,logs,state}

### 10:27 — VPN & Network Verification
- tun0 is up at 10.10.17.114/23, gateway 10.10.16.1 responds to ping (17ms)
- Route to 10.13.37.0/24 exists via tun0 (pushed by HTB VPN server)
- Attempted to start release_arena VPN but `/dev/net/tun` doesn't exist in container (only one TUN device available)
- Existing tun0 already receives routes for 10.13.37.0/24 — same VPN serves both regular and fortress labs

### 10:27 — TCP Full Port Scan (nmap -Pn -p- --min-rate 5000)
- Result: **All 65535 TCP ports filtered** (no-response)
- Scan completed in 28s

### 10:28 — UDP Top 20 Scan (nmap -Pn -sU --top-ports 20)
- All 20 ports show `open|filtered` — inconclusive (no responses either way)

### 10:29 — Targeted SYN Scan (sudo nmap -Pn -sS common ports)
- Ports 22,80,443,3000,5000,8000,8080,8443,9090 all filtered
- curl to http/https on port 80/443 — connection timeout, no response

### 10:30 — Subnet Sweep (10.13.37.10-20, ports 80,443)
- Every IP in range shows filtered — no live hosts responding
- This confirms the machine is NOT running, not a firewall issue on one host

### Assessment
- **The Fortress machine needs to be spawned from the HTB web interface.**
- VPN connectivity is confirmed (gateway responds), but no hosts in 10.13.37.0/24 are online.
- Once spawned, re-run scans.

### Hints from box name "Amazon Fortress"
- Likely involves AWS/cloud services
- Watch for: S3 buckets, EC2 metadata (169.254.169.254), AWS SDK/CLI, IAM credentials, Lambda functions, cloud misconfigurations
