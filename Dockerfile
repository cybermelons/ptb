FROM kalilinux/kali-rolling

RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm openvpn iproute2 \
    nmap gobuster feroxbuster nikto sqlmap \
    python3 python3-pip curl wget git \
    net-tools iputils-ping dnsutils \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @anthropic-ai/claude-code

RUN apt-get update && apt-get install -y --no-install-recommends sudo \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -s /bin/bash hacker \
    && echo 'hacker ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/hacker

RUN printf '#!/bin/sh\necho "protocol=https\nhost=github.com\nusername=x-access-token\npassword=$GITHUB_TOKEN"\n' > /usr/local/bin/git-credential-env && \
    chmod +x /usr/local/bin/git-credential-env

WORKDIR /htb
USER hacker
RUN git config --global credential.helper '/usr/local/bin/git-credential-env'
ENTRYPOINT ["claude", "--dangerously-skip-permissions"]
