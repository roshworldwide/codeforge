"""
CodeForge Configuration
Central settings for JWT, Docker, and application configuration.
"""

import os
import secrets


# ─── JWT Configuration ─────────────────────────────────────────────
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "codeforge-dev-secret-key-change-in-production-2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# ─── Application Settings ──────────────────────────────────────────
APP_NAME = "CodeForge"
APP_VERSION = "1.0.0"
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# ─── Docker Sandbox Settings ───────────────────────────────────────
DOCKER_ENABLED = os.getenv("DOCKER_ENABLED", "true").lower() == "true"
DOCKER_IMAGE = os.getenv("DOCKER_IMAGE", "codeforge-sandbox:latest")
DOCKER_TIMEOUT = int(os.getenv("DOCKER_TIMEOUT", "5"))  # 5 second strict timeout
DOCKER_MEMORY_LIMIT = os.getenv("DOCKER_MEMORY_LIMIT", "128m")
DOCKER_CPU_LIMIT = float(os.getenv("DOCKER_CPU_LIMIT", "0.5"))  # half a core
DOCKER_PIDS_LIMIT = int(os.getenv("DOCKER_PIDS_LIMIT", "50"))
DOCKER_DOCKERFILE_PATH = os.getenv("DOCKER_DOCKERFILE_PATH", "docker/sandbox")

# ─── Execution Settings ────────────────────────────────────────────
MAX_CODE_LENGTH = int(os.getenv("MAX_CODE_LENGTH", "50000"))  # chars
SUBPROCESS_TIMEOUT = int(os.getenv("SUBPROCESS_TIMEOUT", "5"))  # seconds
MAX_OUTPUT_LENGTH = 10000  # chars — truncate stdout/stderr beyond this

# ─── CORS Settings ─────────────────────────────────────────────────
CORS_ORIGINS = ["*"]

# ─── Supported Languages ───────────────────────────────────────────
SUPPORTED_LANGUAGES = {
    "python": {
        "extension": ".py",
        "command": ["python3", "{file}"],
        "display": "Python 3",
    },
    "cpp": {
        "extension": ".cpp",
        "command": ["sh", "-c", "g++ -o /tmp/a.out {file} && /tmp/a.out"],
        "display": "C++ (g++)",
    },
    "javascript": {
        "extension": ".js",
        "command": ["node", "{file}"],
        "display": "JavaScript (Node.js)",
    },
}
