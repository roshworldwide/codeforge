FROM python:3.11-slim

# Install C++ compiler and clean up
RUN apt-get update && \
    apt-get install -y --no-install-recommends g++ && \
    rm -rf /var/lib/apt/lists/*

# Create unprivileged user for code execution
RUN useradd -m -s /bin/bash executor

# Set working directory
WORKDIR /home/executor

# Switch to unprivileged user
USER executor

# Default entrypoint — receives command at runtime
CMD ["echo", "CodeForge Sandbox Ready"]
