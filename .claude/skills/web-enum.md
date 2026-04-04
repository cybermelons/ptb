# Web Enumeration

Goal: map a web application's surface — directories, technologies, entry points, misconfigurations.

## Pre-Checks

Before running any web enumeration:

1. Confirm the port actually serves HTTP: `curl -sI http://<target>:<port>/`
2. Check if HTTPS is available: `curl -skI https://<target>:<port>/`
3. Check `surface.jsonl` for existing web enumeration data on this host:port

## Tech Fingerprinting

Identify the stack before brute-forcing directories — wordlists and techniques depend on it.

```bash
# Response headers — look for Server, X-Powered-By, X-Generator
curl -sI http://<target>/ | grep -iE 'server|powered|generator|framework'

# Common framework markers
curl -s http://<target>/wp-login.php -o /dev/null -w "%{http_code}"    # WordPress
curl -s http://<target>/administrator/ -o /dev/null -w "%{http_code}"   # Joomla
curl -s http://<target>/user/login -o /dev/null -w "%{http_code}"       # Drupal

# JavaScript/frontend clues
curl -s http://<target>/ | grep -oiE '(react|angular|vue|next|nuxt|jquery)[^"]*\.js'
```

Log every technology finding to `surface.jsonl` with type `tech`.

## Directory Enumeration

Match wordlist to identified tech:

```bash
# General-purpose
gobuster dir -u http://<target>/ -w /usr/share/wordlists/dirb/common.txt -t 30 -b 404

# If PHP detected
gobuster dir -u http://<target>/ -w /usr/share/wordlists/dirb/common.txt -x php,phps,php.bak -t 30

# If API detected (JSON responses, /api/ path)
ffuf -u http://<target>/api/FUZZ -w /usr/share/wordlists/dirb/common.txt -mc 200,201,301,302,401,403
```

Log directories with their status codes. A 403 is valuable — it confirms something exists behind auth or a WAF.

## Things To Check On Every Web Target

- `robots.txt` and `sitemap.xml` — often reveal hidden paths
- `.git/HEAD` — exposed git repos are common and critical
- `.env`, `config.php.bak`, `web.config` — leaked config files
- `/server-status`, `/server-info` — Apache status pages
- `/.well-known/` — sometimes reveals infrastructure

```bash
for path in robots.txt sitemap.xml .git/HEAD .env .DS_Store server-status; do
  echo -n "$path: "; curl -so /dev/null -w "%{http_code}" "http://<target>/$path"
  echo
done
```

## Authentication Surfaces

If you find login pages:

- Note the URL and method (form POST, basic auth, token-based)
- Check for default credentials BEFORE brute-forcing
- Check for username enumeration (different responses for valid vs invalid usernames)
- Check for rate limiting before attempting credential attacks
- Log to `surface.jsonl` with type `directory` and note auth requirements

## What NOT To Do

- Don't run gobuster with huge wordlists (rockyou, etc.) as a first pass — start with common.txt
- Don't enumerate directories on non-HTTP services
- Don't ignore 301/302 redirects — follow them, they reveal structure
- Don't forget to check both HTTP and HTTPS if both are available
