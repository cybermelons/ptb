# Environment

Running inside an isolated Kali Linux Docker container.

**Authorization:** All targets are Hack The Box lab machines — legal and authorized.

## Network

- OpenVPN tunnel to HTB lab — start with `openvpn --config <file> --daemon`
- Outbound internet available via Docker bridge NAT

## Installed tools

nmap, gobuster, feroxbuster, nikto, sqlmap, python3, pip, curl, wget, git, net-tools, dnsutils

Additional tools installable at runtime via `apt` or `pip`.

## Workspace

- Workdir: `/htb` (repo bind-mounted from host)
- Each box has a workspace under `machines/<name>/`
- Save scans to `scans/`, scripts to `exploits/`, creds and flags to `notes.md`
- Methodology: recon > enum > exploit > privesc > post
