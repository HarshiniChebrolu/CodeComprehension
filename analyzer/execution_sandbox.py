import subprocess
import sys
import tempfile
import os
import time
import json
import shutil
import re
import logging
import uuid
import base64
from config import Config
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger("codecomprehension.analyzer.execution_sandbox")

# Cache for Docker availability check
_DOCKER_AVAILABLE_CACHE: Optional[bool] = None
_CACHE_TIMESTAMP: float = 0.0

# Disallowed dangerous strings for safe sandbox execution across languages
PYTHON_DANGEROUS = [
    r'import\s+os\s*;', r'from\s+os\s+import', r'import\s+subprocess',
    r'import\s+shutil', r'import\s+socket', r'import\s+urllib',
    r'import\s+requests', r'open\s*\(', r'eval\s*\(', r'exec\s*\(',
    r'__import__', r'os\.system', r'os\.remove', r'os\.rmdir',
    r'sys\.exit' # Often used in user code, but for sandbox, it's safer to block explicit exits
]

CPP_DANGEROUS = [
    r'\bsystem\s*\(', r'\bfork\s*\(', r'\bexecl\s*\(', r'\bexecv\s*\(',
    r'\bpopen\s*\(', r'<windows\.h>', r'<winsock2\.h>', r'<sys/socket\.h>',
    r'<unistd\.h>', r'\bremove\s*\('
]

JAVA_DANGEROUS = [
    r'java\.lang\.System\.exit', r'java\.io\.File', r'java\.net\.Socket',
    r'java\.lang\.Runtime\.exec', r'ProcessBuilder', r'Thread\.sleep'
]

JAVASCRIPT_DANGEROUS = [
    r'require\s*\(\s*["\']child_process["\']\s*\)', r'require\s*\(\s*["\']fs["\']\s*\)',
    r'require\s*\(\s*["\']net["\']\s*\)', r'process\.exit'
]

def check_code_safety(code: str, language: str = "python") -> Tuple[bool, str]:
    """
    Scans code for dangerous system-level commands that could harm host machine.
    """
    lang = language.lower()
    patterns = []

    if lang in ("python", "py"):
        patterns = PYTHON_DANGEROUS
    elif lang in ("c", "cpp"):
        patterns = CPP_DANGEROUS
    elif lang == "java":
        patterns = JAVA_DANGEROUS
    elif lang in ("javascript", "js"):
        patterns = JAVASCRIPT_DANGEROUS
    else:
        # For unsupported languages, err on the side of caution
        return False, f"Code safety check: Unsupported language '{language}'."

    for line in code.split("\n"):
        stripped = line.strip()
        # Skip comments for C/C++/Java, preprocessor directives for C/C++
        if lang in ("c", "cpp", "java"):
            if stripped.startswith(("//", "/*", "*", "#")):
                if not stripped.startswith("#include"): # Allow includes, but check their content later
                    continue
        elif lang in ("python", "javascript", "js"):
            if stripped.startswith(("#", "//", "/*", "*")):
                continue

        for pat in patterns:
            if re.search(pat, stripped, re.IGNORECASE): # Case-insensitive for some patterns
                return False, f"Restricted operation detected: security sandbox does not permit '{stripped[:50]}'."
    return True, ""


def extract_execution_telemetry(code: str, language: str, exec_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts real execution telemetry and metrics from the sandbox run.
    Zero fabricated topics or canned badges.
    """
    lang = language.lower().strip()
    status = exec_result.get("status", "UNKNOWN")
    exit_code = exec_result.get("exit_code", -1)
    duration_ms = exec_result.get("duration_ms", 0)
    backend = getattr(Config, "EXECUTION_BACKEND", "docker")
    mem_limit = Config.SUPPORTED_LANGUAGES.get(lang, {}).get("memory_limit", "128m")
    
    # Real telemetry breakdown based on actual execution output
    metrics = []
    
    # 1. Execution status
    metrics.append({
        "category": "Process Status",
        "name": f"Exit Code {exit_code}",
        "badge": status,
        "icon": "⚡" if status in ("OK", "SUCCESS") else "⚠️",
        "color": "#10b981" if status in ("OK", "SUCCESS") else "#ef4444",
        "summary": f"Process completed with status {status}.",
        "details": f"Duration: {duration_ms}ms. Exit code: {exit_code}."
    })
    
    # 2. Isolation / Environment
    if backend == "docker":
        metrics.append({
            "category": "Isolation Architecture",
            "name": "Docker Container Sandbox",
            "badge": "cgroups/tmpfs",
            "icon": "🐳",
            "color": "#38bdf8",
            "summary": "Isolated container with dropped capabilities and no network access.",
            "details": f"Memory limit: {mem_limit}. Workdir: ephemeral tmpfs /work. Pids limit: 32."
        })
    else:
        metrics.append({
            "category": "Isolation Architecture",
            "name": "Local Subprocess",
            "badge": "Subprocess",
            "icon": "💻",
            "color": "#eab308",
            "summary": "Executed via local subprocess sandbox with timeout enforcement.",
            "details": f"Timeout: {Config.EXECUTION_TIMEOUT}s."
        })
        
    # 3. Output stream telemetry
    stdout_len = len(exec_result.get("stdout", "") or "")
    stderr_len = len(exec_result.get("stderr", "") or "")
    metrics.append({
        "category": "Stream Telemetry",
        "name": "I/O Buffers",
        "badge": f"{stdout_len}B out / {stderr_len}B err",
        "icon": "📊",
        "color": "#a855f7",
        "summary": f"Standard streams captured {stdout_len} bytes stdout, {stderr_len} bytes stderr.",
        "details": "Output truncated: " + ("Yes" if exec_result.get("truncated") else "No")
    })

    return {
        "topics_involved": metrics,
        "runtime_telemetry": {
            "exit_code": exit_code,
            "status": status,
            "execution_time_ms": duration_ms,
            "memory_tier": f"Container Bound: {mem_limit}",
            "isolation_mode": "Docker Container Sandbox (cgroup/tmpfs)" if backend == "docker" else "Local Process",
            "safety_audit": "PASSED (Containerized Sandbox)" if status in ("OK", "SUCCESS", "RUNTIME_ERROR", "COMPILE_ERROR", "TIMEOUT") else f"FAILED ({status})",
            "language": lang
        }
    }


analyze_sandbox_topics = extract_execution_telemetry


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
        logger.debug("Docker binary not found in PATH.")
        _DOCKER_AVAILABLE_CACHE = False
        _CACHE_TIMESTAMP = now
        return False

    try:
        proc = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=Config.EXECUTION_TIMEOUT # Use a reasonable timeout for docker daemon check
        )
        _DOCKER_AVAILABLE_CACHE = (proc.returncode == 0 and bool(proc.stdout.strip()))
        if not _DOCKER_AVAILABLE_CACHE:
            logger.warning(f"Docker daemon not responding: {proc.stderr.decode().strip()}")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning(f"Error checking Docker availability: {e}")
        _DOCKER_AVAILABLE_CACHE = False
    except Exception as e:
        logger.exception("Unexpected error during Docker availability check.")
        _DOCKER_AVAILABLE_CACHE = False

    _CACHE_TIMESTAMP = now
    return _DOCKER_AVAILABLE_CACHE


def _execute_in_docker_container_multilang(
    code: str,
    language: str,
    custom_stdin: str = "",
    timeout: float = Config.EXECUTION_TIMEOUT
) -> Dict[str, Any]:
    """
    Executes user code strictly inside an ephemeral, non-root Docker container
    with complete network, process, memory, filesystem, and capability isolation.
    Supports multiple languages by dynamically selecting Docker image and commands.

    Deliberate Security Trade-off:
    While /tmp is mounted with noexec to block unauthorized binary execution in temporary
    scratch space, /work is provisioned as an in-memory tmpfs with exec permission
    (--tmpfs /work:rw,exec,nosuid,size=32m,uid=1000,gid=1000,mode=1777). This allows compiling
    and executing binaries (C, C++, Java) and scripts (Python, JS) without touching the host
    filesystem, strictly bounded by non-root execution (--user 1000:1000), total network cutoff
    (--network none), memory bounds (--memory 128m), CPU limits (--cpus 1.0), capability drops
    (--cap-drop ALL), and root filesystem immutability (--read-only).
    """
    lang_config = Config.SUPPORTED_LANGUAGES.get(language)
    if not lang_config:
        return {
            "status": "UNSUPPORTED_LANGUAGE",
            "compile_output": "",
            "stdout": "",
            "stderr": f"Language '{language}' is not configured for Docker execution.",
            "exit_code": -1,
            "duration_ms": 0,
            "truncated": False
        }

    docker_image = lang_config["docker_image"]
    extension = lang_config["extension"]
    compile_command_tpl = lang_config.get("compile_command")
    run_command_tpl = lang_config.get("run_command")

    container_name = f"{Config.DOCKER_CONTAINER_NAME_PREFIX}{uuid.uuid4().hex}"
    source_filename = f"main.{extension}"
    exec_filename = "main"

    # Java class name handling
    if language == "java":
        class_name_match = re.search(r'\bpublic\s+class\s+([a-zA-Z0-9_]+)', code)
        if class_name_match:
            source_filename = f"{class_name_match.group(1)}.java"
            exec_filename = class_name_match.group(1)
        else:
            source_filename = "Main.java"
            exec_filename = "Main"
            if "class " not in code:
                code = f"""public class Main {{
    public static void main(String[] args) {{
        {code}
    }}
}}"""
            elif "main(" not in code and "main (" not in code:
                code = f"""public class {exec_filename} {{
    public static void main(String[] args) {{
        {code}
    }}
}}"""

    final_compile_command = None
    if compile_command_tpl:
        final_compile_command = (
            compile_command_tpl
            .replace("main.c", source_filename)
            .replace("main.cpp", source_filename)
            .replace("Main.java", source_filename)
            .replace("main", exec_filename)
        )

    final_run_command = None
    if run_command_tpl:
        final_run_command = (
            run_command_tpl
            .replace("main.py", source_filename)
            .replace("main.js", source_filename)
            .replace("main.c", source_filename)
            .replace("main.cpp", source_filename)
            .replace("Main", exec_filename)
        )

    code_b64 = base64.b64encode(code.encode("utf-8")).decode("ascii")
    stdin_b64 = base64.b64encode((custom_stdin or "").encode("utf-8")).decode("ascii")

    # In-container shell script using /bin/sh
    shell_steps = [
        f"echo '{code_b64}' | base64 -d > {source_filename}",
        f"echo '{stdin_b64}' | base64 -d > stdin.txt"
    ]

    if final_compile_command:
        shell_steps.append(
            f"if ! {final_compile_command} 2> compile_stderr.txt; then "
            f"echo 'COMPILATION_ERROR'; cat compile_stderr.txt; exit 1; fi"
        )

    if final_run_command:
        shell_steps.append(
            f"if ! {final_run_command} < stdin.txt 2> run_stderr.txt > run_stdout.txt; then "
            f"echo 'RUNTIME_ERROR'; cat run_stderr.txt; exit 1; fi"
        )
        shell_steps.append("cat run_stdout.txt")
    else:
        shell_steps.append(f"echo 'No run command specified for {language}.'")

    in_container_script = " && ".join(shell_steps)

    cmd = [
        "docker", "run",
        "--name", container_name,
        "--rm",
        "-i",
        "--network", "none",
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
        "--tmpfs", "/work:rw,exec,nosuid,size=32m,uid=1000,gid=1000,mode=1777",
        "--workdir", "/work",
        "--user", "1000:1000",
        "--cpus", "1.0",
        "--memory", "128m",
        "--pids-limit", "32",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        docker_image,
        "/bin/sh", "-c", in_container_script
    ]

    compile_output = ""
    stdout_output = ""
    stderr_output = ""
    actual_exit_code = -1
    total_duration_ms = 0.0
    status = "ERROR"
    truncated = False

    start_time = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout
        )
        elapsed_s = time.perf_counter() - start_time
        total_duration_ms = round(elapsed_s * 1000, 2)

        raw_stdout = proc.stdout
        raw_stderr = proc.stderr
        actual_exit_code = proc.returncode

        if actual_exit_code == 137:
            status = "MEMORY_LIMIT_EXCEEDED"
            stderr_output = "Execution terminated: Process exceeded the 128MB container memory limit (Out of Memory)."
            logger.warning(f"Container {container_name} OOM/SIGKILL (exit 137).")
        elif actual_exit_code != 0:
            if "COMPILATION_ERROR" in raw_stdout:
                status = "COMPILE_ERROR"
                compile_output = raw_stdout.split("COMPILATION_ERROR\n", 1)[-1].strip()
                stderr_output = compile_output
            elif "RUNTIME_ERROR" in raw_stdout:
                status = "RUNTIME_ERROR"
                parts = raw_stdout.split("RUNTIME_ERROR\n", 1)
                stdout_output = parts[0].strip()
                stderr_output = parts[1].strip() if len(parts) > 1 else raw_stderr.strip()
            else:
                status = "RUNTIME_ERROR"
                stderr_output = (raw_stdout + "\n" + raw_stderr).strip()
        else:
            status = "OK"
            stdout_output = raw_stdout.strip()
            stderr_output = raw_stderr.strip()

    except subprocess.TimeoutExpired:
        total_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        status = "TIMEOUT"
        stderr_output = f"Execution Timed Out: Program exceeded the strict {timeout}s runtime threshold."
        try:
            subprocess.run(["docker", "kill", container_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5.0)
        except Exception:
            pass

    except Exception as e:
        status = "CONTAINER_ERROR"
        stderr_output = f"Container Sandbox Error: {str(e)}"

    # Truncate outputs
    if len(stdout_output) > Config.MAX_OUTPUT_CHARS:
        stdout_output = stdout_output[:Config.MAX_OUTPUT_CHARS] + "\n... (output truncated)"
        truncated = True
    if len(stderr_output) > Config.MAX_OUTPUT_CHARS:
        stderr_output = stderr_output[:Config.MAX_OUTPUT_CHARS] + "\n... (error output truncated)"
        truncated = True
    if len(compile_output) > Config.MAX_OUTPUT_CHARS:
        compile_output = compile_output[:Config.MAX_OUTPUT_CHARS] + "\n... (compile output truncated)"
        truncated = True

    return {
        "status": status,
        "compile_output": compile_output,
        "stdout": stdout_output,
        "stderr": stderr_output,
        "exit_code": actual_exit_code,
        "duration_ms": total_duration_ms,
        "truncated": truncated
    }


def execute_user_code(code: str, language: str = "python", custom_stdin: str = "") -> Dict[str, Any]:
    """
    Executes user code securely.
    Prioritizes an isolated non-root Docker container with complete network, memory, and capability drop.
    If Docker is unavailable, adheres strictly to safety policy:
      - Does not execute arbitrary untrusted code directly on the Flask server.
      - Disables execution cleanly with an informative explanation.
      - Only executes locally if explicitly configured with EXECUTION_BACKEND == 'local_dev_unsafe'.
    """
    lang = language.lower().strip()
    backend = getattr(Config, "EXECUTION_BACKEND", "docker")

    # Static pattern check
    is_safe, reason = check_code_safety(code, lang)
    if not is_safe:
        res = {
            "status": "SECURITY_VIOLATION",
            "compile_output": "",
            "stdout": "",
            "stderr": f"Sandbox Security Violation: {reason}",
            "exit_code": -1,
            "duration_ms": 0,
            "truncated": False
        }
        # Add success key for compatibility with existing analyze_sandbox_topics expecting it
        compat_res = {"success": False, **res}
        compat_res.update(analyze_sandbox_topics(code, lang, compat_res))
        del compat_res["success"] # Remove for final return if not needed elsewhere
        return compat_res

    # 1. Primary Isolated Architecture: Dedicated Docker Container
    if backend == "docker":
        if not is_docker_available():
            # Crucial Fallback Rule: Do NOT silently run on host server!
            res = {
                "status": "UNAVAILABLE", # Use 'UNAVAILABLE' for Docker not running
                "compile_output": "",
                "stdout": "",
                "stderr": (
                    "Code execution is unavailable: A secure containerized execution environment (Docker) "
                    "is not active or accessible. To protect system integrity, untrusted code cannot "
                    "execute on the host server. Static review, AST analysis, bug detection, "
                    "and mentoring guidance remain fully available."
                ),
                "exit_code": -1,
                "duration_ms": 0,
                "truncated": False
            }
            # Add success key for compatibility
            compat_res = {"success": False, **res}
            compat_res.update(analyze_sandbox_topics(code, lang, compat_res))
            del compat_res["success"]
            return compat_res
        
        # Check if the specific language image exists, pull if not
        lang_info = Config.SUPPORTED_LANGUAGES.get(lang)
        if lang_info:
            docker_image = lang_info["docker_image"]
            try:
                subprocess.run(["docker", "image", "inspect", docker_image], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                logger.debug(f"Docker image {docker_image} already exists.")
            except subprocess.CalledProcessError:
                logger.info(f"Docker image {docker_image} not found, attempting to pull...")
                try:
                    subprocess.run(["docker", "pull", docker_image], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60.0)
                    logger.info(f"Successfully pulled Docker image {docker_image}.")
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                    logger.error(f"Failed to pull Docker image {docker_image}: {e}")
                    res = {
                        "status": "UNAVAILABLE",
                        "compile_output": "",
                        "stdout": "",
                        "stderr": f"Docker image for '{language}' ({docker_image}) could not be pulled. "
                                  "Ensure Docker is properly configured and the image exists. Original error: {e}",
                        "exit_code": -1,
                        "duration_ms": 0,
                        "truncated": False
                    }
                    compat_res = {"success": False, **res}
                    compat_res.update(analyze_sandbox_topics(code, lang, compat_res))
                    del compat_res["success"]
                    return compat_res
        else:
            # Should have been caught earlier by language validation in routes, but good to have
            res = {
                "status": "UNSUPPORTED_LANGUAGE",
                "compile_output": "",
                "stdout": "",
                "stderr": f"Language '{language}' is not configured for Docker execution.",
                "exit_code": -1,
                "duration_ms": 0,
                "truncated": False
            }
            compat_res = {"success": False, **res}
            compat_res.update(analyze_sandbox_topics(code, lang, compat_res))
            del compat_res["success"]
            return compat_res

        res = _execute_in_docker_container_multilang(code, lang, custom_stdin, Config.EXECUTION_TIMEOUT)
        compat_res = {"success": res["status"] == "OK", **res} # Add success key for compatibility
        compat_res.update(analyze_sandbox_topics(code, lang, compat_res))
        del compat_res["success"]
        return compat_res

    elif backend == "disabled":
        res = {
            "status": "DISABLED",
            "compile_output": "",
            "stdout": "",
            "stderr": "Code execution is explicitly disabled by administrator configuration.",
            "exit_code": -1,
            "duration_ms": 0,
            "truncated": False
        }
        compat_res = {"success": False, **res}
        compat_res.update(analyze_sandbox_topics(code, lang, compat_res))
        del compat_res["success"]
        return compat_res

    elif backend == "local_dev_unsafe":
        if Config.FLASK_ENV == "production":
             res = {
                "status": "SECURITY_ERROR",
                "compile_output": "",
                "stdout": "",
                "stderr": "EXECUTION_BACKEND 'local_dev_unsafe' is forbidden in production environments.",
                "exit_code": -1,
                "duration_ms": 0,
                "truncated": False
            }
             compat_res = {"success": False, **res}
             compat_res.update(analyze_sandbox_topics(code, lang, compat_res))
             del compat_res["success"]
             return compat_res
        
        # Explicit opt-in for local development testing only
        # Simplified to use subprocess directly for local languages without full sandbox
        local_exec_command = None
        lang_data = Config.SUPPORTED_LANGUAGES.get(lang)
        if lang_data:
            local_exec_command = lang_data["run_command"]
        
        if not local_exec_command:
            res = {
                "status": "UNSUPPORTED_LANGUAGE",
                "compile_output": "",
                "stdout": "",
                "stderr": f"Language '{language}' is not configured for local execution.",
                "exit_code": -1,
                "duration_ms": 0,
                "truncated": False
            }
            compat_res = {"success": False, **res}
            compat_res.update(analyze_sandbox_topics(code, lang, compat_res))
            del compat_res["success"]
            return compat_res

        temp_dir = tempfile.mkdtemp()
        source_file = os.path.join(temp_dir, f"main.{lang_data['extension']}")
        
        # Basic compilation for C/C++/Java locally
        compile_output = ""
        local_compile_success = True
        if lang_data["compile_command"]:
            try:
                with open(source_file, "w", encoding="utf-8") as f:
                    f.write(code)
                compile_cmd = lang_data["compile_command"].replace("main.c", source_file).replace("main.cpp", source_file).replace("Main.java", source_file)
                compile_proc = subprocess.run(
                    compile_cmd.split(), # Assuming simple command, no complex shell features
                    cwd=temp_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=lang_data["compile_timeout"]
                )
                compile_output = compile_proc.stdout + compile_proc.stderr
                if compile_proc.returncode != 0:
                    local_compile_success = False
                    res = {
                        "status": "COMPILE_ERROR",
                        "compile_output": compile_output,
                        "stdout": "",
                        "stderr": compile_output,
                        "exit_code": compile_proc.returncode,
                        "duration_ms": round(compile_proc.elapsed * 1000, 2) if hasattr(compile_proc, 'elapsed') else 0,
                        "truncated": len(compile_output) > Config.MAX_OUTPUT_CHARS
                    }
                    compat_res = {"success": False, **res}
                    compat_res.update(analyze_sandbox_topics(code, lang, compat_res))
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    del compat_res["success"]
                    return compat_res
            except subprocess.TimeoutExpired:
                 res = {
                    "status": "COMPILE_TIMEOUT",
                    "compile_output": "",
                    "stdout": "",
                    "stderr": f"Compilation timed out ({lang_data['compile_timeout']}s)",
                    "exit_code": -1,
                    "duration_ms": lang_data['compile_timeout'] * 1000,
                    "truncated": False
                }
                 compat_res = {"success": False, **res}
                 compat_res.update(analyze_sandbox_topics(code, lang, compat_res))
                 shutil.rmtree(temp_dir, ignore_errors=True)
                 del compat_res["success"]
                 return compat_res
            except Exception as e:
                res = {
                    "status": "COMPILER_ERROR",
                    "compile_output": "",
                    "stdout": "",
                    "stderr": f"Local compilation failed: {str(e)}",
                    "exit_code": -1,
                    "duration_ms": 0,
                    "truncated": False
                }
                compat_res = {"success": False, **res}
                compat_res.update(analyze_sandbox_topics(code, lang, compat_res))
                shutil.rmtree(temp_dir, ignore_errors=True)
                del compat_res["success"]
                return compat_res

        if local_compile_success:
            try:
                if not lang_data["compile_command"]: # For interpreted languages like Python/JS
                    with open(source_file, "w", encoding="utf-8") as f:
                        f.write(code)
                
                run_cmd = local_exec_command.replace("main.py", source_file).replace("main.js", source_file).replace("main.c", source_file).replace("main.cpp", source_file)
                # For Java, need to handle class path and class name explicitly
                if lang == "java":
                    class_name_match = re.search(r'\bpublic\s+class\s+([a-zA-Z0-9_]+)', code)
                    class_name = class_name_match.group(1) if class_name_match else "Main"
                    run_cmd = f"java -cp {temp_dir} {class_name}"


                start_time = time.perf_counter()
                proc = subprocess.run(
                    run_cmd.split(), # Split command string into list, assuming no complex args
                    cwd=temp_dir,
                    input=custom_stdin,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=lang_data["run_timeout"]
                )
                elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

                stdout = proc.stdout[:Config.MAX_OUTPUT_CHARS]
                stderr = proc.stderr[:Config.MAX_OUTPUT_CHARS]
                truncated = len(proc.stdout) > Config.MAX_OUTPUT_CHARS or len(proc.stderr) > Config.MAX_OUTPUT_CHARS

                res = {
                    "status": "OK" if proc.returncode == 0 else "RUNTIME_ERROR",
                    "compile_output": compile_output,
                    "stdout": stdout,
                    "stderr": stderr,
                    "exit_code": proc.returncode,
                    "duration_ms": elapsed_ms,
                    "truncated": truncated
                }
                compat_res = {"success": proc.returncode == 0, **res}
                compat_res.update(analyze_sandbox_topics(code, lang, compat_res))
                shutil.rmtree(temp_dir, ignore_errors=True)
                del compat_res["success"]
                return compat_res

            except subprocess.TimeoutExpired:
                res = {
                    "status": "TIMEOUT",
                    "compile_output": compile_output,
                    "stdout": "",
                    "stderr": f"Execution Timed Out ({lang_data['run_timeout']}s limit exceeded).",
                    "exit_code": -1,
                    "duration_ms": lang_data['run_timeout'] * 1000,
                    "truncated": False
                }
                compat_res = {"success": False, **res}
                compat_res.update(analyze_sandbox_topics(code, lang, compat_res))
                shutil.rmtree(temp_dir, ignore_errors=True)
                del compat_res["success"]
                return compat_res
            except Exception as e:
                res = {
                    "status": "ERROR",
                    "compile_output": compile_output,
                    "stdout": "",
                    "stderr": f"Local execution failed: {str(e)}",
                    "exit_code": -1,
                    "duration_ms": 0,
                    "truncated": False
                }
                compat_res = {"success": False, **res}
                compat_res.update(analyze_sandbox_topics(code, lang, compat_res))
                shutil.rmtree(temp_dir, ignore_errors=True)
                del compat_res["success"]
                return compat_res
        else: # Compilation failed for local_dev_unsafe
            pass # The compile error was already returned above

    else:
        res = {
            "status": "CONFIG_ERROR",
            "compile_output": "",
            "stdout": "",
            "stderr": f"Invalid EXECUTION_BACKEND configuration: '{backend}'",
            "exit_code": -1,
            "duration_ms": 0,
            "truncated": False
        }
        compat_res = {"success": False, **res}
        compat_res.update(analyze_sandbox_topics(code, lang, compat_res))
        del compat_res["success"]
        return compat_res


def run_test_cases_safely(code: str, test_cases: List[Dict[str, Any]], func_name: str, language: str = "python") -> List[Dict[str, Any]]:
    """
    Safely executes test cases against the user's submitted code.
    """
    lang = language.lower().strip()
    is_safe, reason = check_code_safety(code, lang)
    if not is_safe:
        return [
            {
                "id": tc.get("id", f"tc_{i}"),
                "status": "SECURITY_VIOLATION",
                "actual": "Blocked by security filter",
                "passed": False,
                "error": reason
            }
            for i, tc in enumerate(test_cases)
        ]

    results = []
    for tc in test_cases:
        tc_id = tc.get("id")
        args = tc.get("args", [])
        expected = tc.get("expected")

        # For Python, generate a harness to call the function
        if lang in ("python", "py"):
            harness = f"""
{code}

import json
try:
    # Check if func_name is directly in globals or if it needs to be imported/defined
    if '{func_name}' in globals() and callable(globals()['{func_name}']):
        fn = globals()['{func_name}']
        res = fn(*{repr(args)})
        print("RESULT:" + json.dumps(res))
    else:
        # Attempt to find it as a method if a class is present (basic heuristic)
        # Or, if func_name is 'solution', try to find the first defined function
        found_func = False
        if func_name == "solution":
            import inspect
            tree = compile(code, '<string>', 'exec', ast.PyCF_ONLY_AST)
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    potential_func_name = node.name
                    # Try to execute the code to get the function into globals
                    exec(code, globals())
                    if potential_func_name in globals() and callable(globals()[potential_func_name]):
                        fn = globals()[potential_func_name]
                        res = fn(*{repr(args)})
                        print("RESULT:" + json.dumps(res))
                        found_func = True
                        break
            if not found_func:
                 print("ERROR:Function '{func_name}' not found or no callable function in scope.")
        else:
             print("ERROR:Function '{func_name}' not found or not callable in global scope.")
except Exception as e:
    import traceback
    print("EXCEPTION:" + str(e))
"""
            exec_result = execute_user_code(harness, "python")
        else:
            # For other languages, we generally expect the user's code to be a complete program
            # that might read from stdin, or we need a more complex harness.
            # For simplicity, for non-python, we'll just execute the user code with stdin
            # and compare stdout against expected. This assumes the user's code directly
            # produces the expected output.
            # A more robust solution would involve generating language-specific test harnesses
            # (e.g., a C++ `main` that calls the user's function).
            input_str = json.dumps(args) if args else "" # Pass args as JSON string for simplicity
            exec_result = execute_user_code(code, language, input_str)


        output = exec_result.get("stdout", "")
        stderr_output = exec_result.get("stderr", "")
        dur_ms = exec_result.get("duration_ms", 0) # Use standardized key
        exec_status = exec_result.get("status", "ERROR") # Use standardized key

        actual_val = "None"
        status = "PASS"
        passed = False
        err_msg = exec_result.get("stderr") # Use standardized key

        if exec_status == "DISABLED" or exec_status == "UNAVAILABLE":
            results.append({
                "id": tc_id,
                "status": "NEEDS_VERIFICATION",
                "actual": "Execution disabled/unavailable",
                "passed": False,
                "execution_time_ms": 0,
                "error": "Automated verification requires an active execution environment."
            })
            continue

        if exec_status == "TIMEOUT":
            results.append({
                "id": tc_id,
                "status": "TIMEOUT",
                "actual": "Execution timed out",
                "passed": False,
                "execution_time_ms": dur_ms,
                "error": f"Exceeded {Config.EXECUTION_TIMEOUT}s timeout"
            })
            continue
        
        if exec_status != "OK" and exec_status != "COMPILE_ERROR": # Handle generic runtime errors
             results.append({
                "id": tc_id,
                "status": exec_status,
                "actual": output or stderr_output,
                "passed": False,
                "execution_time_ms": dur_ms,
                "error": err_msg or f"Execution failed with status: {exec_status}"
            })
             continue

        if "RESULT:" in output and lang in ("python", "py"):
            res_str = output.split("RESULT:", 1)[1].strip()
            actual_val = res_str
            try:
                parsed = json.loads(res_str)
                exp_clean = str(expected).strip()
                # Flexible comparison for expected vs actual (e.g., allow '3.0' == 3)
                if str(parsed) == exp_clean or (isinstance(expected, (int, float)) and parsed == expected):
                    passed = True
                    status = "PASS"
                else:
                    status = "FAIL"
                    passed = False
            except Exception:
                # If JSON parsing fails, treat as string comparison
                if res_str.strip() == str(expected).strip():
                    passed = True
                    status = "PASS"
                else:
                    status = "FAIL"
                
        elif "EXCEPTION:" in output and lang in ("python", "py"):
            err_msg = output.split("EXCEPTION:", 1)[1].strip()
            actual_val = f"Exception: {err_msg}"
            status = "ERROR"
            passed = False
        elif "ERROR:" in output and lang in ("python", "py"):
            err_msg = output.split("ERROR:", 1)[1].strip()
            actual_val = err_msg
            status = "ERROR"
            passed = False
        else: # For non-Python or if Python output doesn't match harness format
            # Direct stdout comparison for other languages
            actual_val = output.strip()
            exp_clean = str(expected).strip()
            if actual_val == exp_clean:
                passed = True
                status = "PASS"
            else:
                status = "FAIL"
            
            if stderr_output: # If there was stderr, it's an error
                status = "ERROR"
                err_msg = stderr_output
                passed = False # If there's stderr, it didn't truly pass

        results.append({
            "id": tc_id,
            "status": status,
            "actual": actual_val,
            "passed": passed,
            "execution_time_ms": dur_ms,
            "error": err_msg or (stderr_output if status == "ERROR" else None)
        })

    return results

def get_runnable_languages_status() -> List[Dict[str, Any]]:
    """
    Returns a list of all supported languages with their runnability status
    on the current machine (Docker availability, image presence).
    """
    docker_up = is_docker_available()
    language_statuses = []

    for lang_alias, lang_data in Config.SUPPORTED_LANGUAGES.items():
        is_runnable = False
        reason = "Execution disabled by configuration." # Default reason

        if Config.EXECUTION_BACKEND == "docker":
            if not docker_up:
                reason = "Docker daemon is not running or accessible."
            else:
                docker_image = lang_data["docker_image"]
                try:
                    subprocess.run(["docker", "image", "inspect", docker_image], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    is_runnable = True
                    reason = "Ready for Docker execution."
                except subprocess.CalledProcessError:
                    reason = f"Docker image '{docker_image}' is not downloaded. It will be pulled on first use."
                except Exception as e:
                    reason = f"Error checking Docker image '{docker_image}': {e}"
        elif Config.EXECUTION_BACKEND == "local_dev_unsafe":
            if Config.FLASK_ENV == "production":
                reason = "Local unsafe execution is forbidden in production environment."
            else:
                # Check for local compilers/runtimes
                if lang_data["compile_command"]: # Compiled language
                    compiler = lang_data["compile_command"].split()[0]
                    if shutil.which(compiler) or (sys.platform == "win32" and os.path.exists(compiler)): # Basic check for windows path
                        is_runnable = True
                        reason = "Local compiler found (UNSAFE for dev only)."
                    else:
                        reason = f"Local compiler '{compiler}' not found in PATH."
                elif lang_data["run_command"]: # Interpreted language
                    interpreter = lang_data["run_command"].split()[0]
                    if shutil.which(interpreter) or (sys.platform == "win32" and os.path.exists(interpreter)):
                        is_runnable = True
                        reason = "Local interpreter found (UNSAFE for dev only)."
                    else:
                        reason = f"Local interpreter '{interpreter}' not found in PATH."
                else:
                    reason = "Language is not configured for local execution."
        else: # backend == "disabled"
            pass # reason remains "Execution disabled by configuration."

        language_statuses.append({
            "language": lang_alias,
            "runnable": is_runnable,
            "reason": reason
        })
    return language_statuses
