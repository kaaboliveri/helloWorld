import os
import subprocess
import shutil # Keep for other potential tools, though not used in execute_code_tool directly
import asyncio # Ensure asyncio is imported
from pathlib import Path
from typing import Optional # Add Optional if not already there
from openai_agents.tool import tool, ToolError # Ensure these are imported
from .. import config

# (Keep _resolve_sandbox_path and _needs_confirmation as they are)

# --- Conceptual Security Hardening Strategies (Overall for this module) ---
# 1. Principle of Least Privilege:
#    - If Maity runs as a service, ensure the service user has minimal necessary permissions on the system.
#    - The `LOCAL_SANDBOX_DIR` should have strict permissions, writable only by this user.
# 2. Audit Logging:
#    - All file operations (read, write, list) and code/command executions should be logged securely
#      with timestamps, user identifiers (if applicable), and command details.
# 3. Configuration-driven Security:
#    - Features like `REQUIRE_CONFIRMATION_LOCAL` are good. Extend this for:
#        - Whitelisting/blacklisting specific commands or executables.
#        - Whitelisting/blacklisting readable/writable paths *within* the sandbox.
#        - Setting resource quotas (CPU, memory, time, network access) for executed code.

def _resolve_sandbox_path(user_path: str) -> Path:
    # Within _resolve_sandbox_path, the existing check is good:
    # `if sandbox_root not in full_path.parents and full_path != sandbox_root:`
    # Additional checks could include:
    # - Preventing use of symlinks that could point outside the sandbox if not handled by `resolve()`.
    # - Ensuring no part of the path contains forbidden characters or sequences.
    sandbox_root = Path(config.LOCAL_SANDBOX_DIR).resolve()
    # Allow user_path to be '.' to refer to the sandbox_root itself
    if user_path == ".":
        full_path = sandbox_root
    else:
        full_path = (sandbox_root / user_path).resolve()

    # CRITICAL: Ensure the resolved path is still within the sandbox
    if full_path != sandbox_root and sandbox_root not in full_path.parents:
        raise ToolError(tool_name="local_system", message=f"Security Error: Path '{user_path}' is outside the allowed sandbox.")
    return full_path

def _needs_confirmation(action_type: str) -> bool:
    print(f"CONFIRMATION REQUIRED for action: {action_type}. Auto-approving for now (DANGEROUS).")
    return config.REQUIRE_CONFIRMATION_LOCAL

# (Keep list_files_tool, read_file_tool, write_file_tool as they are)
# For read_file_tool and write_file_tool, current size limits and path resolution are good starting points.
# Further hardening:
# - For `write_file_tool`: Sanitize content being written if it's interpreted elsewhere (e.g., prevent writing executable scripts that are later run without checks).
# - For `read_file_tool`: Be cautious if file content is passed directly to LLMs without sanitization/truncation, as it could be very large or contain harmful prompts.

@tool("Lists files and directories within a specified path inside the sandbox.")
async def list_files_tool(path: str = ".") -> str:
    print(f"Executing list_files_tool for path: {path}")
    try:
        target_path = _resolve_sandbox_path(path)
        if not target_path.is_dir():
            raise ToolError(tool_name="list_files_tool", message=f"Path '{path}' is not a valid directory.")
        contents = [f.name + ("/" if f.is_dir() else "") for f in target_path.iterdir()]
        return f"Contents of '{path}':\n" + "\n".join(contents) if contents else f"Directory '{path}' is empty."
    except Exception as e:
        print(f"Error in list_files_tool: {e}")
        raise ToolError(tool_name="list_files_tool", message=f"Failed to list files in '{path}'. Ensure path is valid and within the sandbox.")

@tool("Reads the content of a text file within the sandbox.")
async def read_file_tool(path: str) -> str:
    print(f"Executing read_file_tool for path: {path}")
    try:
        target_path = _resolve_sandbox_path(path)
        if not target_path.is_file():
             raise ToolError(tool_name="read_file_tool", message=f"File '{path}' not found or is not a file.")
        max_size = 1024 * 1024
        if target_path.stat().st_size > max_size:
             raise ToolError(tool_name="read_file_tool", message=f"File '{path}' is too large (>{max_size} bytes).")
        content = target_path.read_text(encoding='utf-8')
        return content
    except Exception as e:
        print(f"Error in read_file_tool: {e}")
        raise ToolError(tool_name="read_file_tool", message=f"Failed to read file '{path}'. Ensure path is valid and within the sandbox.")

@tool("Writes content to a text file within the sandbox, potentially overwriting.")
async def write_file_tool(path: str, content: str) -> str:
    print(f"Executing write_file_tool for path: {path}")
    if config.REQUIRE_CONFIRMATION_LOCAL:
        if not _needs_confirmation(f"write file '{path}'"):
            raise ToolError(tool_name="write_file_tool", message="Action denied by user confirmation requirement.")
    try:
        target_path = _resolve_sandbox_path(path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding='utf-8')
        return f"Successfully wrote content to '{path}'."
    except Exception as e:
        print(f"Error in write_file_tool: {e}")
        raise ToolError(tool_name="write_file_tool", message=f"Failed to write file '{path}'. Ensure path is valid and within the sandbox.")


@tool("Executes a code snippet (e.g., Python, Shell) in a sandboxed environment.")
async def execute_code_tool(code: str, language: str = "python", timeout_seconds: Optional[int] = None) -> str: # Added timeout_seconds
    # Use a module-level default or config-based default if timeout_seconds is None
    effective_timeout = timeout_seconds if timeout_seconds is not None else 30 # Default to 30s

    print(f"Executing execute_code_tool for language: {language} with timeout: {effective_timeout}s")
    # ... (existing initial parameter validation, confirmation checks) ...
    if config.REQUIRE_CONFIRMATION_LOCAL:
         if not _needs_confirmation(f"execute {language} code"):
             raise ToolError(tool_name="execute_code_tool", message="Action denied by user confirmation requirement.")
    if language not in ["python", "shell", "bash"]:
        raise ToolError(tool_name="execute_code_tool", message=f"Unsupported language: {language}.")

    # --- Conceptual Security Hardening for `execute_code_tool` ---
    # This tool is the most critical from a security perspective.
    # Current sandboxing (writing to temp file in LOCAL_SANDBOX_DIR and running) is very basic.
    #
    # 1. Containerization (Strongest Isolation):
    #    - Execute the code within a dedicated, short-lived Docker container.
    #    - The container should have:
    #        - A minimal filesystem (e.g., based on Alpine Linux).
    #        - No network access by default, or strictly limited egress.
    #        - Read-only access to necessary parts of the sandbox (if code needs to read files).
    #        - Write access only to a specific output directory within its own filesystem.
    #        - Strict resource limits (CPU, memory, execution time via Docker run options).
    #        - Run as a non-root user inside the container.
    #    - Maity would need Docker installed and permissions to manage containers (Docker-in-Docker if Maity itself is containerized, or access to host Docker socket - carefully).
    #    - Example flow: Create Dockerfile for chosen language -> Build image (if not cached) -> Run container with code -> Capture stdout/stderr -> Remove container.
    #
    # 2. System Call Filtering / Seccomp / AppArmor (Advanced Linux):
    #    - If not using full containerization, use OS-level sandboxing features.
    #    - `seccomp-bpf` can restrict the system calls the executed process can make.
    #    - AppArmor or SELinux profiles can further confine the process.
    #    - This is complex to set up correctly and maintain per language/use-case.
    #
    # 3. Stricter Input Sanitization for `code` and `language`:
    #    - `language`: Ensure it's from a very small, hardcoded allowlist.
    #    - `code` (especially for 'shell'):
    #        - Disallow or heavily sanitize metacharacters if not using direct script execution (e.g., `|`, `&`, `;`, `$()`, ``` ` ```).
    #        - The current approach of writing to a script file (`temp_maity_script.sh/py`) and executing that file
    #          (e.g., `sh temp_maity_script.sh`) is generally safer than `subprocess.run(code, shell=True)`.
    #
    # 4. Ephemeral Execution Environments:
    #    - Ensure that each execution is in a clean state. The temporary script files are a good start.
    #    - If not using containers, ensure no state persists between executions within the sandbox that could be exploited.
    #
    # 5. Output Sanitization (already partially done with truncation):
    #    - Besides truncation, scan output for sensitive information if there's a risk of the code
    #      exposing environment details (though if sandboxed properly, this risk is lower).
    #
    # 6. Language-Specific Sandboxing:
    #    - Python: Can explore using restricted execution modules or techniques, but they are often not foolproof.
    #      Running in a separate process with OS-level controls is more reliable.
    #    - JavaScript (if Node.js execution were added): Use `vm` module with caution, or better, separate process.

    sandbox_dir = Path(config.LOCAL_SANDBOX_DIR).resolve()
    result = ""
    max_output_length = getattr(config, 'EXECUTE_CODE_MAX_OUTPUT_LENGTH', 10000)

    script_path = None
    process = None # Initialize process

    try:
        if language == "python":
            script_path = sandbox_dir / "temp_maity_script.py"
            script_path.write_text(code, encoding='utf-8')
            process = await asyncio.create_subprocess_exec(
                'python', str(script_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(sandbox_dir)
            )
        elif language in ["shell", "bash"]:
            script_path = sandbox_dir / "temp_maity_script.sh"
            script_path.write_text(code, encoding='utf-8')
            os.chmod(script_path, 0o755)
            # Determine shell to use (bash if specified, otherwise sh)
            shell_executable = 'bash' if language == 'bash' else 'sh'
            process = await asyncio.create_subprocess_exec(
                shell_executable, str(script_path), # Pass script as argument to shell
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(sandbox_dir)
            )

        stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=effective_timeout) # Use effective_timeout
        return_code = process.returncode

        stdout = stdout_bytes.decode('utf-8', errors='replace')
        stderr = stderr_bytes.decode('utf-8', errors='replace')

        output_parts = []
        output_parts.append(f"Exit Code: {return_code}")

        current_length = len(output_parts[0])

        if stdout:
            # Max length for stdout, leaving space for "--- STDOUT ---..." and potential stderr header
            stdout_header = "--- STDOUT ---"
            stdout_truncate_msg = "... (stdout truncated)"
            # Max possible length for stdout text itself
            max_stdout_text_len = max_output_length - current_length - len(stdout_header) - 50 # 50 for stderr header and other formatting

            if len(stdout) > max_stdout_text_len:
                output_parts.append(f"{stdout_header}{'(first ' + str(max_stdout_text_len) + ' chars)'}\n{stdout[:max_stdout_text_len]}")
                output_parts.append(stdout_truncate_msg)
            else:
                output_parts.append(f"{stdout_header}\n{stdout}")
        else:
            output_parts.append("--- STDOUT ---\n(empty)")

            current_length += len(output_parts[-1]) # +1 for newlines if joining with \n later

        if stderr:
            stderr_header = "--- STDERR ---"
            stderr_truncate_msg = "... (stderr truncated)"
            # Max possible length for stderr text itself, accounting for its header and potential truncation message
            # Approx length of header + truncation msg: len(stderr_header) + len("(first X chars)\n") + len(stderr_truncate_msg) -> ~40-50 chars
            max_stderr_text_len = max(0, max_output_length - current_length - len(stderr_header) - 50)

            if max_stderr_text_len == 0 : # No meaningful space left for stderr
                 output_parts.append(f"{stderr_header}\n... (output truncated, no space for stderr details)")
            elif len(stderr) > max_stderr_text_len:
                output_parts.append(f"{stderr_header}{'(first ' + str(max_stderr_text_len) + ' chars)'}\n{stderr[:max_stderr_text_len]}")
                output_parts.append(stderr_truncate_msg)
            else:
                output_parts.append(f"{stderr_header}\n{stderr}")
        else:
            output_parts.append("--- STDERR ---\n(empty)")

        result = "\n".join(output_parts)

    except asyncio.TimeoutError:
        if process and process.returncode is None:
            try: process.kill(); await process.wait()
            except ProcessLookupError: pass
        result = f"Execution timed out after {effective_timeout} seconds." # Use effective_timeout
    except Exception as e:
        # print(f"Error in execute_code_tool: {e}") # Already printed by the agent runner usually
        result = f"Failed to execute code: {type(e).__name__} - {e}"
    finally:
        if script_path and script_path.exists():
             try: script_path.unlink()
             except OSError as e: print(f"Warning: Could not delete temp script {script_path}: {e}")

    # Final length check on the entire result string
    if len(result) > max_output_length:
        result = result[:max_output_length - len("... (overall output truncated)...") -5] + "\n... (overall output truncated)" # Ensure space for truncation msg

    return result.strip()


# Keep run_shell_command_tool as is, or explicitly mark as deprecated if desired by modifying its docstring further.
@tool("Runs a single shell command in the sandboxed environment.")
async def run_shell_command_tool(command: str) -> str:
    """
    DEPRECATED - Use execute_code_tool(language='shell') instead for better control and safety.
    ...
    """
    # --- Conceptual Security Hardening for `run_shell_command_tool` (if it were to be kept) ---
    # 1. Deprecation is Key: Strongly advise against its use.
    # 2. Strict Command Whitelisting: If kept for very specific, trusted use cases,
    #    only allow commands from a very short, hardcoded whitelist.
    # 3. Argument Sanitization/Escaping: If commands take arguments, these must be meticulously
    #    sanitized or escaped to prevent command injection. `shlex.split` can help parse,
    #    and `shlex.quote` can help quote arguments for safe inclusion if building command strings.
    #    However, passing arguments as a list to `subprocess` functions (like `*cmd_parts`)
    #    is generally safer than building a single command string with `shell=True`.
    # 4. Avoid `shell=True` at all costs if not absolutely necessary and understood. The current
    #    implementation correctly avoids `shell=True` by splitting the command.

    print(f"WARNING: Executing DANGEROUS run_shell_command_tool: {command}")
    process = None # Initialize process
    if config.REQUIRE_CONFIRMATION_LOCAL:
        if not _needs_confirmation(f"run shell command: {command[:50]}..."):
            raise ToolError(tool_name="run_shell_command_tool", message="Action denied by user confirmation requirement.")
    try:
        cmd_parts = command.split()
        if not cmd_parts:
            raise ToolError(tool_name="run_shell_command_tool", message="Empty command provided.")

        sandbox_dir = Path(config.LOCAL_SANDBOX_DIR).resolve()
        timeout_seconds = 15
        process = await asyncio.create_subprocess_exec(
            *cmd_parts,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(sandbox_dir)
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
        return_code = process.returncode

        max_len_shell = 2000
        stdout_str = stdout.decode('utf-8', errors='replace')
        stderr_str = stderr.decode('utf-8', errors='replace')

        # Truncate stdout and stderr individually
        truncated_stdout = stdout_str[:max_len_shell]
        stdout_note = "... (truncated)" if len(stdout_str) > max_len_shell else ""

        # Adjust max_len for stderr based on stdout length
        remaining_len_for_stderr = max(0, max_len_shell - len(truncated_stdout) - len(stdout_note) - 50) # 50 for headers
        truncated_stderr = stderr_str[:remaining_len_for_stderr]
        stderr_note = "... (truncated)" if len(stderr_str) > remaining_len_for_stderr else ""

        return f"Exit Code: {return_code}\n--- STDOUT ---\n{truncated_stdout}{stdout_note}\n--- STDERR ---\n{truncated_stderr}{stderr_note}"

    except asyncio.TimeoutError:
         if process and process.returncode is None:
            try:
                process.kill()
                await process.wait()
            except ProcessLookupError:
                pass
         return f"Command timed out after {timeout_seconds} seconds."
    except FileNotFoundError:
        raise ToolError(tool_name="run_shell_command_tool", message=f"Command not found: '{cmd_parts[0]}'. Ensure it's available in the environment.")
    except Exception as e:
        print(f"Error in run_shell_command_tool: {e}")
        raise ToolError(tool_name="run_shell_command_tool", message=f"Failed to run command '{command}': {e}")

    # The current use of `*cmd_parts` (after `command.split()`) is better than `shell=True`,
    # but `command.split()` is naive for complex commands with quoted arguments.
    # `shlex.split(command)` would be more robust for parsing.

    # The return string formatting was updated in a previous step to include stdout_note and stderr_note
    # For example: return f"Exit Code: {return_code}\n--- STDOUT ---\n{truncated_stdout}{stdout_note}\n--- STDERR ---\n{truncated_stderr}{stderr_note}"
    # This part of the code is not being changed by this specific comment insertion task, so it's just a note.
    pass # Placeholder to ensure the diff tool has a non-empty replace block if needed.
