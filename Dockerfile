FROM kalilinux/kali-rolling

RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm openvpn iproute2 \
    nmap gobuster feroxbuster nikto sqlmap \
    python3 python3-pip curl wget git \
    net-tools iputils-ping dnsutils \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @anthropic-ai/claude-code

WORKDIR /htb
ENTRYPOINT ["claude"]
