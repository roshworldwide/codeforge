FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends g++ && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash executor

WORKDIR /home/executor

USER executor

CMD ["echo", "CodeForge Sandbox Ready"]
