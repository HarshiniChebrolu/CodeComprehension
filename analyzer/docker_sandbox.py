import subprocess
import shutil
import time
import logging
from typing import Dict, Any
from config import Config

logger = logging.getLogger("codecomprehension.sandbox")
_DOCKER_AVAILABLE_CACHE = None
_CACHE_TIMESTAMP = 0.0


def is_docker_available() -> bool:
    """
    Checks if Docker CLI is installed and the Docker daemon is actively responding.
    Caches availability status for 15 seconds to avoid subprocess latency on every call.
    """
    global _DOCKER_AVAILABLE_CACHE, _CACHE_TIMESTAMP
    now = time.time()
    if _DOCKER_AVAILABLE_CACHE is not None and (now - _CACHE_TIMESTAMP < 15.0):
        return _DOCKER_AVAILABLE_CACHE

    docker_bin = shutil.which("docker") or shutil.which("docker.exe")
    if not docker_bin:
        _DOCKER_AVAILABLE_CACHE = False
        _CACHE_TIMESTAMP = now
        return False

    try:
        proc = subprocess.run(
            ["docker", "version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5.0
        )
        _DOCKER_AVAILABLE_CACHE = (proc.returncode == 0)
    except Exception:
        _DOCKER_AVAILABLE_CACHE = False

    _CACHE_TIMESTAMP = now
    return _DOCKER_AVAILABLE_CACHE


def execute_in_docker_container(
    code: str,
    language: str = "python",
    custom_stdin: str = "",
    timeout: float = 15.0
) -> Dict[str, Any]:
    """
    Executes user code strictly inside an ephemeral, non-root Docker container
    with complete network, process, memory, filesystem, and capability isolation.

    Isolation Controls:
      - --network none             (No inbound/outbound networking)
      - --read-only                (Read-only root filesystem)
      - --tmpfs /tmp:rw,noexec,nosuid,size=16m (Ephemeral memory-only scratchpad)
      - --user 1000:1000           (Non-root execution)
      - --cpus 1.0                 (CPU core bound)
      - --memory 128m              (128 MB RAM envelope)
      - --pids-limit 32            (Fork bomb protection)
      - --cap-drop ALL             (Drops all Linux capabilities)
      - --security-opt no-new-privileges (Blocks privilege escalation)
      - --rm                       (Auto cleanup on exit)
      - No host directory mounts   (Host filesystem completely inaccessible)
      - Code fed via STDIN         (Zero shell interpolation or temp file leaks)
    """
    lang = language.lower().strip()
    if lang not in ("python", "py"):
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Docker container sandbox currently only supports Python. Selected: {language}",
            "execution_time_ms": 0,
            "status": "UNSUPPORTED_LANGUAGE",
            "isolation_mode": "Docker Isolated Container",
            "exit_code": -1
        }

    # Prepare execution wrapper: safely injects custom_stdin into sys.stdin stream
    runner_script = (
        "import sys, io\n"
        f"__stdin_payload__ = {repr(custom_stdin)}\n"
        "sys.stdin = io.StringIO(__stdin_payload__)\n"
        + code
    )

    cmd = [
        "docker", "run",
        "--rm",
        "-i",
        "--network", "none",
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
        "--user", "1000:1000",
        "--cpus", "1.0",
        "--memory", "128m",
        "--pids-limit", "32",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "python:3.12-alpine",
        "python", "-u", "-"
    ]

    start_time = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            input=runner_script,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout
        )
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        stdout = proc.stdout[:Config.MAX_OUTPUT_CHARS]
        stderr = proc.stderr[:Config.MAX_OUTPUT_CHARS]
        exit_code = proc.returncode

        # Exit code 137 in Docker indicates killed by OOM or SIGKILL
        if exit_code == 137:
            return {
                "success": False,
                "stdout": stdout,
                "stderr": "Execution terminated: Process exceeded the 128MB container memory limit (Out of Memory).",
                "execution_time_ms": elapsed_ms,
                "status": "MEMORY_LIMIT_EXCEEDED",
                "isolation_mode": "Docker Isolated Container (OOM Bounded)",
                "exit_code": 137
            }

        return {
            "success": (exit_code == 0),
            "stdout": stdout,
            "stderr": stderr,
            "execution_time_ms": elapsed_ms,
            "status": "PASS" if exit_code == 0 else "RUNTIME_ERROR",
            "isolation_mode": "Docker Isolated Container (Network=None, ReadOnly=True, NonRoot=True)",
            "exit_code": exit_code
        }

    except subprocess.TimeoutExpired:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Execution Timed Out: Program exceeded the strict {timeout}s runtime threshold.",
            "execution_time_ms": elapsed_ms,
            "status": "TIMEOUT",
            "isolation_mode": "Docker Isolated Container (Terminated on Timeout)",
            "exit_code": -9
        }
    except Exception as e:
        logger.exception("Failed to execute in Docker sandbox: %s", e)
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Container Sandbox Error: {str(e)}",
            "execution_time_ms": 0,
            "status": "CONTAINER_ERROR",
            "isolation_mode": "Docker Container Error",
            "exit_code": -1
        }
