# Environment

Running inside an isolated Kali Linux Docker container.

**Authorization:** All targets are Hack The Box lab machines — legal and authorized.

## Credentials

- `$GITHUB_TOKEN` — GitHub PAT, available as env var inside the container

## Network

- OpenVPN tunnel to HTB lab — start with `sudo openvpn --config <file> --daemon --log /tmp/openvpn.log --pull-filter ignore "ifconfig-ipv6" --pull-filter ignore "route-ipv6" --pull-filter ignore "tun-ipv6"`
- Outbound internet available via Docker bridge NAT

## Installed tools

nmap, gobuster, feroxbuster, nikto, sqlmap, python3, pip, curl, wget, git, net-tools, dnsutils

Additional tools installable at runtime via `apt` or `pip`.

## Workspace

- Workdir: `/htb` (repo bind-mounted from host)
- Each box has a workspace under `machines/<name>/`
- Save scans to `scans/`, scripts to `exploits/`, creds and flags to `notes.md`
- Methodology: recon > enum > exploit > privesc > post
