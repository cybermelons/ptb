# Recon

Goal: discover what exists in the target environment. Hosts, ports, services, rough topology.

## Workflow

1. Check `.scope.yml` for target ranges and exclusions
2. Check `./state/surface.jsonl` — don't re-discover what you already know
3. Start broad, narrow down

## Host Discovery

```bash
# Ping sweep — fast, may miss hosts that block ICMP
nmap -sn <range>

# ARP discovery — local subnet only, more reliable
nmap -PR -sn <range>

# DNS brute force — if you have a domain
gobuster dns -d <domain> -w /usr/share/wordlists/subdomains-top1million-5000.txt -t 30
```

After host discovery, append each live host to `surface.jsonl` before moving on.

## Port Scanning

Scan in stages, not all at once:

```bash
# Stage 1: fast top-1000 TCP scan
nmap -sS -top-ports 1000 --open <target>

# Stage 2: service version detection on open ports only
nmap -sV -p <open_ports_from_stage_1> <target>

# Stage 3: full 65535 port scan (only if initial scan is thin)
nmap -sS -p- --min-rate 1000 <target>

# UDP — targeted, not full range (UDP scans are slow)
nmap -sU --top-ports 50 <target>
```

Don't run stage 3 by default. Only if the top-1000 scan returned very few ports and you suspect more are open.

## Service Fingerprinting

When `nmap -sV` gives you a service, log the exact version string. If it says "http" without a product:

```bash
# Grab banner directly
curl -sI http://<target>:<port>/ | head -20
nc -w3 <target> <port>
```

## DNS Enumeration

If you have a domain name:

```bash
dig ANY <domain>
dig axfr <domain> @<nameserver>   # zone transfer — often denied, always try
host -t MX <domain>
host -t TXT <domain>
```

## What to Log

Every discovery → `surface.jsonl` with type `host`, `service`, `dns`, or `cert`. Every new attack surface element should generate at least one entry in `unexplored.jsonl` for later enumeration.

## When to Stop Recon

Move to Enumeration when you have:
- A list of live hosts
- Open ports with service versions on key targets
- DNS records if a domain is in scope

Don't aim for perfection. You can return to recon later with new access.

## Decision Trees

### New box / IP change?
```
1. WIPE old entries from /etc/hosts first. grep -v hostname /etc/hosts > /tmp/h && sudo cp /tmp/h /etc/hosts
2. Add ONE entry for new IP.
3. Verify: curl --connect-timeout 3 http://hostname/
4. If curl hangs but ping works → check /etc/hosts for stale entries.
```
