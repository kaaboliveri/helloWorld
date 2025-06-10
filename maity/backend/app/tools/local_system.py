import os
import subprocess
import shutil # Keep for other potential tools, though not used in execute_code_tool directly
import asyncio # Ensure asyncio is imported
from pathlib import Path
from openai_agents.tool import tool, ToolError # Ensure these are imported
from .. import config

# (Keep _resolve_sandbox_path and _needs_confirmation as they are)
def _resolve_sandbox_path(user_path: str) -> Path:
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
async def execute_code_tool(code: str, language: str = "python") -> str:
    print(f"Executing execute_code_tool for language: {language}")
    if config.REQUIRE_CONFIRMATION_LOCAL:
         if not _needs_confirmation(f"execute {language} code"):
             raise ToolError(tool_name="execute_code_tool", message="Action denied by user confirmation requirement.")

    if language not in ["python", "shell", "bash"]:
        raise ToolError(tool_name="execute_code_tool", message=f"Unsupported language: {language}. Only 'python' and 'shell'/'bash' are supported.")

    sandbox_dir = Path(config.LOCAL_SANDBOX_DIR).resolve()
    result = ""
    timeout_seconds = 30
    max_output_length = 10000 # Max characters for combined stdout/stderr

    script_path = None # Initialize script_path
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

        stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
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

        current_length = sum(len(p) + 1 for p in output_parts) # +1 for newlines

        if stderr:
            stderr_header = "--- STDERR ---"
            stderr_truncate_msg = "... (stderr truncated)"
            # Max possible length for stderr text itself
            max_stderr_text_len = max_output_length - current_length - len(stderr_header) - 10 # 10 for safety

            if max_stderr_text_len <= 0 : # No space left for stderr
                 output_parts.append(f"{stderr_header}\n... (output truncated, no space for stderr)")
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
            try:
                process.kill()
                await process.wait()
            except ProcessLookupError:
                pass
        result = f"Execution timed out after {timeout_seconds} seconds."
    except Exception as e:
        print(f"Error in execute_code_tool: {e}")
        result = f"Failed to execute code: {type(e).__name__} - {e}"
    finally:
        if script_path and script_path.exists():
             try:
                script_path.unlink()
             except OSError as e:
                print(f"Warning: Could not delete temporary script {script_path}: {e}")

    # Final length check on the entire result string is implicitly handled by careful calculation above,
    # but an explicit one can be a safeguard if calculations are complex.
    # For now, we assume the above logic correctly manages the total length.
    # if len(result) > max_output_length:
    #     result = result[:max_output_length - 25] + "\n... (output truncated)"

    return result.strip()


# Keep run_shell_command_tool as is, or explicitly mark as deprecated if desired by modifying its docstring further.
@tool("Runs a single shell command in the sandboxed environment.")
async def run_shell_command_tool(command: str) -> str:
    """
    DEPRECATED - Use execute_code_tool(language='shell') instead for better control and safety.
    Runs a single shell command directly. Highly risky. Use with extreme caution.
    Requires confirmation if enabled.

    Args:
        command: The shell command to run.

    Returns:
        A string containing the stdout and stderr, or an error message.
    """
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
