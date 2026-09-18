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

_docker_client = None
_image_verified = False


def _get_docker_client():
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

    try:
        dockerfile_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            DOCKER_DOCKERFILE_PATH,
        )

        if not os.path.isdir(dockerfile_dir):
            logger.error(f"Dockerfile directory not found: {dockerfile_dir}")
            return False

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


async def execute_code(code: str, language: str, stdin: str = "") -> Dict:
    if len(code) > MAX_CODE_LENGTH:
        return _error_result(
            f"Code exceeds maximum length of {MAX_CODE_LENGTH:,} characters"
        )

    if language not in SUPPORTED_LANGUAGES:
        return _error_result(
            f"Unsupported language: {language}. "
            f"Supported: {', '.join(SUPPORTED_LANGUAGES.keys())}"
        )

    if DOCKER_ENABLED:
        image_ready = await _ensure_image_exists()
        if image_ready:
            return await _execute_docker(code, language, stdin)
        else:
            logger.warning("Docker image unavailable — falling back to subprocess")

    return await _execute_subprocess(code, language, stdin)


async def _execute_docker(code: str, language: str, stdin: str = "") -> Dict:
    client = _get_docker_client()
    if not client:
        return await _execute_subprocess(code, language, stdin)

    lang_config = SUPPORTED_LANGUAGES[language]
    start_time = time.time()
    container = None

    try:
        filename = f"code{lang_config['extension']}"

        code_b64 = base64.b64encode(code.encode("utf-8")).decode("ascii")

        cmd_parts = lang_config["command"]
        if cmd_parts[0] == "sh" and cmd_parts[1] == "-c":
            exec_cmd = cmd_parts[2].replace("{file}", f"/tmp/{filename}")
        else:
            exec_cmd = " ".join(
                part.replace("{file}", f"/tmp/{filename}")
                for part in cmd_parts
            )

        shell_script = (
            f"echo '{code_b64}' | base64 -d > /tmp/{filename} && {exec_cmd}"
        )

        loop = asyncio.get_event_loop()
        container = await loop.run_in_executor(
            None,
            lambda: client.containers.run(
                image=DOCKER_IMAGE,
                command=["sh", "-c", shell_script],
                detach=True,
                remove=False,
                network_disabled=True,
                mem_limit=DOCKER_MEMORY_LIMIT,
                nano_cpus=int(DOCKER_CPU_LIMIT * 1e9),
                pids_limit=DOCKER_PIDS_LIMIT,
                read_only=True,
                tmpfs={"/tmp": "size=64M,exec"},
                security_opt=["no-new-privileges"],
                cap_drop=["ALL"],
                user="executor",
            ),
        )

        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: container.wait(timeout=DOCKER_TIMEOUT),
                ),
                timeout=DOCKER_TIMEOUT + 2,
            )

            exit_code = result.get("StatusCode", -1)

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
        if "not found" in str(e).lower():
            return _error_result(
                f"Docker image '{DOCKER_IMAGE}' not found. Please run: "
                f"docker build -t {DOCKER_IMAGE} docker/sandbox/"
            )
        return await _execute_subprocess(code, language, stdin)

    finally:
        if container:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: container.remove(force=True),
                )
            except Exception:
                pass


async def _execute_subprocess(code: str, language: str, stdin: str = "") -> Dict:
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


def _error_result(message: str, duration: int = 0) -> Dict:
    return {
        "stdout": "",
        "stderr": message,
        "exit_code": 1,
        "status": "error",
        "duration": duration,
        "engine": "none",
    }


def _format_stderr(stderr: str, language: str) -> str:
    if not stderr:
        return ""

    stderr = stderr[:MAX_OUTPUT_LENGTH]

    stderr = stderr.replace("/tmp/code.py", "code.py")
    stderr = stderr.replace("/tmp/code.cpp", "code.cpp")
    stderr = stderr.replace("/tmp/code.js", "code.js")
    stderr = stderr.replace("/tmp/a.out", "program")

    return stderr
