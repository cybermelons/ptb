# DevArea - 10.129.16.166

## Host Info
- OS: Linux (TTL=63, likely Ubuntu)
- Hostname: devarea.htb

## Open Ports

| Port | Service | Version | Notes |
|------|---------|---------|-------|
| 21   | FTP     | vsftpd 3.0.5 | Anonymous login allowed, `pub/employee-service.jar` |
| 22   | SSH     | OpenSSH 9.6p1 Ubuntu | |
| 80   | HTTP    | Apache 2.4.58 | Redirects to `http://devarea.htb/`, static job board site |
| 8080 | HTTP    | Jetty 9.4.27 | Apache CXF SOAP service at `/employeeservice` |
| 8500 | HTTP    | Go net/http | Proxy server (Hoverfly proxy port) |
| 8888 | HTTP    | Go net/http | Hoverfly Dashboard (requires auth — 401) |

## FTP Loot
- `employee-service.jar` — Apache CXF 3.2.14 SOAP web service (Java 8)
- Classes: `htb.devarea.{ServerStarter, EmployeeService, EmployeeServiceImpl, Report}`
- Single endpoint: `submitReport(Report)` — takes employeeName, department, content, confidential

## SOAP Service (port 8080)
- WSDL: `http://10.129.16.166:8080/employeeservice?wsdl`
- Accepts `submitReport` with Report object (employeeName, department, content, confidential)
- Responds with string containing the submitted data — reflects input back

## Hoverfly (ports 8500/8888)
- Port 8888: Dashboard (401 Unauthorized)
- Port 8500: Proxy server
- Hoverfly is an API simulation/service virtualization tool

## Exploitation Chain
1. **CVE-2022-46364** — CXF SSRF via MTOM XOP:Include → read local files (file:// protocol)
2. Read `/etc/systemd/system/hoverfly.service` → found Hoverfly creds: `admin:O7IJ27MyyXiU`
3. **CVE-2025-54123** — Hoverfly middleware RCE → code execution as `dev_ryan`
4. Planted SSH key → persistent access

## Creds
- Hoverfly admin: `admin` / `O7IJ27MyyXiU`
- SSH: `dev_ryan` via key (`machines/target/dev_ryan_key`)

## Privesc to syswatch
5. Found `/home/dev_ryan/syswatch-v1.zip` — full source code!
6. Hidden `/service-status` endpoint has **command injection** (shell=True + weak regex)
7. Regex blocks `;/\.&<>\A-Z` but allows `|`, `$()`, newlines, backticks
8. Used `echo hex | xxd -r -p | python3` to run arbitrary code as syswatch

## Privesc to root
9. Created symlink: `logs/system.log` → `plugins/root_monitor.sh` (syswatch can write to logs/)
10. Ran `sudo syswatch.sh plugin cpu_mem_monitor.sh $'\ncp /bin/bash /tmp/rootbash3\nchmod 4755 /tmp/rootbash3'`
    - Newline in args caused `log_message` (running as ROOT) to write payload through symlink
    - Created `plugins/root_monitor.sh` with our bash commands
11. `syswatch-monitor.timer` (5 min cron) runs ALL `*.sh` in plugins/ as ROOT
12. SUID bash created → root shell

## Flags
- User: `95528e4df12447619aa7f7798aa3af54`
- Root: `0acae446a3d5a902120d351343663f02`
