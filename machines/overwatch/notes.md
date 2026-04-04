# Overwatch — 10.129.244.81

## FLAGS
- User: pending
- Root: pending

## Recon

- TTL=127 → Windows box
- nmap binary blocked (Operation not permitted), used bash /dev/tcp scan
- Open ports (common range): 53, 88, 135, 139, 389, 445, 464, 636, 3389, 5985
- This is a **Domain Controller** (88=Kerberos, 389=LDAP, 636=LDAPS, 53=DNS, 445=SMB)
- WinRM available (5985), RDP available (3389)
- Full port scan (10001-65535) not yet completed
- No HTTP on 80/443/8080/8443

## TODO
- Banner grab on key services (SMB, LDAP, DNS)
- Enumerate domain name via LDAP/SMB
- Check anonymous SMB/LDAP access
- Add domain name to /etc/hosts
- Full port scan still needed
