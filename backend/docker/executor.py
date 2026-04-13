"""
╔══════════════════════════════════════════════════════════════════╗
║  CodeForge Docker Executor v2.0                                  ║
║  Secure, ephemeral container execution with auto-build           ║
║                                                                  ║
║  Strategy:                                                       ║
║    1. Docker SDK spins up a hardened container per request       ║
║    2. Code is injected via shell heredoc → /tmp/code.<ext>      ║
║    3. Container runs with --rm, --network none, --read-only,    ║
║       --cap-drop ALL, strict mem/cpu/pid limits                 ║
║    4. 5-second hard kill for infinite loops                     ║
║    5. Subprocess fallback only if Docker unavailable            ║
╚══════════════════════════════════════════════════════════════════╝
"""

import asyncio
import base64
import os
import tempfile
import time
import logging
from typing import Dict, Optional

from backend.config import (
    DOCKER_ENABLED,
    DOCKER_IMAGE,
    DOCKER_TIMEOUT,
    DOCKER_MEMORY_LIMIT,
    DOCKER_CPU_LIMIT,
    DOCKER_PIDS_LIMIT,
    DOCKER_DOCKERFILE_PATH,
    SUBPROCESS_TIMEOUT,
    SUPPORTED_LANGUAGES,
    MAX_CODE_LENGTH,
    MAX_OUTPUT_LENGTH,
)

logger = logging.getLogger("codeforge.executor")

# ─── Module-Level State ─────────────────────────────────────────────
_docker_client = None
_image_verified = False


def _get_docker_client():
    """Lazy-initialize and cache the Docker client singleton."""
    global _docker_client
    if _docker_client is None:
        try:
            import docker as docker_sdk
            _docker_client = docker_sdk.from_env()
            _docker_client.ping()
            logger.info("✅ Docker client connected")
        except Exception as e:
            logger.warning(f"Docker unavailable: {e}")
            _docker_client = None
    return _docker_client


async def _ensure_image_exists():
    """
    Check if the sandbox image exists; if not, auto-build it
    from the Dockerfile. Only checks once per server lifecycle.
    """
    global _image_verified
    if _image_verified:
        return True

    client = _get_docker_client()
    if not client:
        return False

    try:
        client.images.get(DOCKER_IMAGE)
        _image_verified = True
        logger.info(f"✅ Sandbox image '{DOCKER_IMAGE}' found")
        return True
    except Exception:
        logger.info(f"🔧 Sandbox image '{DOCKER_IMAGE}' not found — building...")

    # Auto-build from Dockerfile
    try:
        dockerfile_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            DOCKER_DOCKERFILE_PATH,
        )

        if not os.path.isdir(dockerfile_dir):
            logger.error(f"Dockerfile directory not found: {dockerfile_dir}")
            return False

        # Build in a thread to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        image, build_logs = await loop.run_in_executor(
            None,
            lambda: client.images.build(
                path=dockerfile_dir,
                tag=DOCKER_IMAGE,
                rm=True,
                forcerm=True,
            ),
        )
        _image_verified = True
        logger.info(f"✅ Sandbox image '{DOCKER_IMAGE}' built successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to build sandbox image: {e}")
        return False


# ─── Public API ──────────────────────────────────────────────────────

async def execute_code(code: str, language: str, stdin: str = "") -> Dict:
    """
    Execute user code securely and return results.
    Docker-first with subprocess fallback.
    """
    # ── Input validation ──
    if len(code) > MAX_CODE_LENGTH:
        return _error_result(
            f"Code exceeds maximum length of {MAX_CODE_LENGTH:,} characters"
        )

    if language not in SUPPORTED_LANGUAGES:
        return _error_result(
            f"Unsupported language: {language}. "
            f"Supported: {', '.join(SUPPORTED_LANGUAGES.keys())}"
        )

    # ── Route to execution engine ──
    if DOCKER_ENABLED:
        image_ready = await _ensure_image_exists()
        if image_ready:
            return await _execute_docker(code, language, stdin)
        else:
            logger.warning("Docker image unavailable — falling back to subprocess")

    return await _execute_subprocess(code, language, stdin)


# ─── Docker Execution ───────────────────────────────────────────────

async def _execute_docker(code: str, language: str, stdin: str = "") -> Dict:
    """
    Execute code in an ephemeral Docker container with strict security.

    Container lifecycle:
      1. Create container with hardened security profile
      2. Inject code via base64 to avoid shell escaping issues
      3. Wait for exit or kill after timeout
      4. Capture stdout/stderr
      5. Container auto-removed via `--rm` equivalent
    """
    client = _get_docker_client()
    if not client:
        return await _execute_subprocess(code, language, stdin)

    lang_config = SUPPORTED_LANGUAGES[language]
    start_time = time.time()
    container = None

    try:
        filename = f"code{lang_config['extension']}"

        # Encode code as base64 to safely pass through shell without escaping issues
        code_b64 = base64.b64encode(code.encode("utf-8")).decode("ascii")

        # Build the execution command, handling both simple and compound (sh -c) commands
        cmd_parts = lang_config["command"]
        if cmd_parts[0] == "sh" and cmd_parts[1] == "-c":
            # Compound command (e.g., C++: "sh -c 'g++ -o /tmp/a.out {file} && /tmp/a.out'")
            # Extract the shell script and do replacement directly
            exec_cmd = cmd_parts[2].replace("{file}", f"/tmp/{filename}")
        else:
            # Simple command (e.g., Python: "python3 {file}")
            exec_cmd = " ".join(
                part.replace("{file}", f"/tmp/{filename}")
                for part in cmd_parts
            )

        shell_script = (
            f"echo '{code_b64}' | base64 -d > /tmp/{filename} && {exec_cmd}"
        )

        # Run container in a thread pool to avoid blocking asyncio
        loop = asyncio.get_event_loop()
        container = await loop.run_in_executor(
            None,
            lambda: client.containers.run(
                image=DOCKER_IMAGE,
                command=["sh", "-c", shell_script],
                detach=True,              # Don't block — we manage the wait
                remove=False,             # We remove manually after capturing logs
                network_disabled=True,    # No internet access
                mem_limit=DOCKER_MEMORY_LIMIT,
                nano_cpus=int(DOCKER_CPU_LIMIT * 1e9),  # 0.5 CPU = 500_000_000 ns
                pids_limit=DOCKER_PIDS_LIMIT,
                read_only=True,           # Root FS is read-only
                tmpfs={"/tmp": "size=64M,exec"},
                security_opt=["no-new-privileges"],
                cap_drop=["ALL"],
                user="executor",
            ),
        )

        # Wait for container to finish with strict timeout
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: container.wait(timeout=DOCKER_TIMEOUT),
                ),
                timeout=DOCKER_TIMEOUT + 2,  # asyncio grace period
            )

            exit_code = result.get("StatusCode", -1)

            # Capture logs
            stdout = await loop.run_in_executor(
                None,
                lambda: container.logs(stdout=True, stderr=False)
                .decode("utf-8", errors="replace"),
            )
            stderr = await loop.run_in_executor(
                None,
                lambda: container.logs(stdout=False, stderr=True)
                .decode("utf-8", errors="replace"),
            )

            duration = int((time.time() - start_time) * 1000)

            # Check for OOM kill
            if exit_code == 137:
                return {
                    "stdout": stdout[:MAX_OUTPUT_LENGTH],
                    "stderr": "⚠ Process killed — out of memory (128MB limit exceeded)\n",
                    "exit_code": 137,
                    "status": "error",
                    "duration": duration,
                    "engine": "docker",
                }

            return {
                "stdout": stdout[:MAX_OUTPUT_LENGTH],
                "stderr": _format_stderr(stderr, language),
                "exit_code": exit_code,
                "status": "success" if exit_code == 0 else "error",
                "duration": duration,
                "engine": "docker",
            }

        except (asyncio.TimeoutError, Exception) as timeout_err:
            # Kill the runaway container
            try:
                await loop.run_in_executor(None, lambda: container.kill())
            except Exception:
                pass

            duration = int((time.time() - start_time) * 1000)

            return {
                "stdout": "",
                "stderr": (
                    f"⏱ Execution timed out after {DOCKER_TIMEOUT} seconds.\n"
                    f"Your code may contain an infinite loop or a long-running operation.\n"
                    f"Tip: Check your loop conditions and add base cases to recursive functions."
                ),
                "exit_code": -1,
                "status": "timeout",
                "duration": duration,
                "engine": "docker",
            }

    except Exception as e:
        logger.error(f"Docker execution error: {e}")
        duration = int((time.time() - start_time) * 1000)
        # Graceful fallback to subprocess on Docker API errors
        if "not found" in str(e).lower():
            return _error_result(
                f"Docker image '{DOCKER_IMAGE}' not found. Please run: "
                f"docker build -t {DOCKER_IMAGE} docker/sandbox/"
            )
        return await _execute_subprocess(code, language, stdin)

    finally:
        # Always clean up the container (ephemeral / --rm behavior)
        if container:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: container.remove(force=True),
                )
            except Exception:
                pass


# ─── Subprocess Fallback ─────────────────────────────────────────────

async def _execute_subprocess(code: str, language: str, stdin: str = "") -> Dict:
    """
    Fallback execution using subprocess when Docker is unavailable.
    """
    lang_config = SUPPORTED_LANGUAGES[language]
    start_time = time.time()

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=lang_config["extension"],
        delete=False,
        dir=tempfile.gettempdir(),
    ) as f:
        f.write(code)
        code_file = f.name

    try:
        cmd = [part.replace("{file}", code_file) for part in lang_config["command"]]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=stdin.encode() if stdin else None),
                timeout=SUBPROCESS_TIMEOUT,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            duration = int((time.time() - start_time) * 1000)
            return {
                "stdout": "",
                "stderr": (
                    f"⏱ Execution timed out after {SUBPROCESS_TIMEOUT} seconds.\n"
                    f"Tip: Check your loop conditions and add base cases to recursive functions."
                ),
                "exit_code": -1,
                "status": "timeout",
                "duration": duration,
                "engine": "subprocess",
            }

        duration = int((time.time() - start_time) * 1000)
        exit_code = process.returncode

        return {
            "stdout": stdout.decode("utf-8", errors="replace")[:MAX_OUTPUT_LENGTH],
            "stderr": _format_stderr(
                stderr.decode("utf-8", errors="replace"), language
            ),
            "exit_code": exit_code,
            "status": "success" if exit_code == 0 else "error",
            "duration": duration,
            "engine": "subprocess",
        }

    except FileNotFoundError:
        duration = int((time.time() - start_time) * 1000)
        return _error_result(
            f"Runtime for '{language}' not found on this machine.\n"
            f"The Docker sandbox has all runtimes pre-installed.",
            duration=duration,
        )
    except Exception as e:
        duration = int((time.time() - start_time) * 1000)
        return _error_result(f"Execution error: {str(e)}", duration=duration)
    finally:
        try:
            os.unlink(code_file)
        except OSError:
            pass


# ─── Helpers ─────────────────────────────────────────────────────────

def _error_result(message: str, duration: int = 0) -> Dict:
    """Build a standardized error result."""
    return {
        "stdout": "",
        "stderr": message,
        "exit_code": 1,
        "status": "error",
        "duration": duration,
        "engine": "none",
    }


def _format_stderr(stderr: str, language: str) -> str:
    """
    Clean up stderr for student-friendly display.
    Strips noisy container paths and keeps relevant error info.
    """
    if not stderr:
        return ""

    # Truncate
    stderr = stderr[:MAX_OUTPUT_LENGTH]

    # Clean up temp file paths — replace container paths with cleaner names
    stderr = stderr.replace("/tmp/code.py", "code.py")
    stderr = stderr.replace("/tmp/code.cpp", "code.cpp")
    stderr = stderr.replace("/tmp/code.js", "code.js")
    stderr = stderr.replace("/tmp/a.out", "program")

    return stderr
