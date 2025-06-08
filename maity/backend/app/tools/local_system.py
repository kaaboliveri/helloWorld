import os
import subprocess
import shutil
from pathlib import Path
from openai_agents.tool import tool, ToolError
from .. import config # Import config for sandbox path and confirmation settings

# --- Security Warning ---
# Interacting with the local file system and executing code/commands is
# EXTREMELY DANGEROUS if not implemented with strict security measures.
# The following are basic placeholders and MUST be enhanced with:
# 1. Robust path validation to prevent directory traversal (../).
# 2. Strict confinement within the defined LOCAL_SANDBOX_DIR.
# 3. Input sanitization for commands and code.
# 4. Resource limits (CPU, memory, time) for execution.
# 5. User confirmation for sensitive actions (write, delete, execute) if configured.
# 6. Consider running execution in isolated containers (Docker-in-Docker or similar).

def _resolve_sandbox_path(user_path: str) -> Path:
    """Resolves a user-provided path against the sandbox root."""
    sandbox_root = Path(config.LOCAL_SANDBOX_DIR).resolve()
    full_path = (sandbox_root / user_path).resolve()

    # CRITICAL: Ensure the resolved path is still within the sandbox
    if sandbox_root not in full_path.parents and full_path != sandbox_root:
        raise ToolError(tool_name="local_system", message=f"Security Error: Path '{user_path}' is outside the allowed sandbox.")
    return full_path

def _needs_confirmation(action_type: str) -> bool:
    """Check if user confirmation is needed for this action."""
    # TODO: Implement actual user confirmation mechanism (e.g., via websocket/API callback)
    print(f"CONFIRMATION REQUIRED for action: {action_type}. Auto-approving for now (DANGEROUS).")
    return config.REQUIRE_CONFIRMATION_LOCAL # Placeholder - This needs real interaction

# --- Tool Definitions ---

@tool("Lists files and directories within a specified path inside the sandbox.")
async def list_files_tool(path: str = ".") -> str:
    """
    Lists the contents (files and directories) of a specified path relative
    to the Maity sandbox directory. Defaults to the sandbox root.

    Args:
        path: The relative path within the sandbox (e.g., 'project_x', '.').

    Returns:
        A string listing the contents, or an error message.
    """
    print(f"Executing list_files_tool for path: {path}")
    try:
        target_path = _resolve_sandbox_path(path)
        if not target_path.is_dir():
            raise ToolError(tool_name="list_files_tool", message=f"Path '{path}' is not a valid directory.")

        contents = [f.name + ("/" if f.is_dir() else "") for f in target_path.iterdir()]
        return f"Contents of '{path}':\n" + "\n".join(contents) if contents else f"Directory '{path}' is empty."

    except Exception as e:
        print(f"Error in list_files_tool: {e}")
        # Don't leak internal paths in error messages to the user/LLM
        raise ToolError(tool_name="list_files_tool", message=f"Failed to list files in '{path}'. Ensure path is valid and within the sandbox.")

@tool("Reads the content of a text file within the sandbox.")
async def read_file_tool(path: str) -> str:
    """
    Reads the content of a specified text file located relative to the Maity
    sandbox directory.

    Args:
        path: The relative path to the file within the sandbox (e.g., 'my_notes.txt').

    Returns:
        The content of the file as a string, or an error message.
    """
    print(f"Executing read_file_tool for path: {path}")
    try:
        target_path = _resolve_sandbox_path(path)
        if not target_path.is_file():
             raise ToolError(tool_name="read_file_tool", message=f"File '{path}' not found or is not a file.")

        # Add size limits to prevent reading huge files
        max_size = 1024 * 1024 # 1MB limit example
        if target_path.stat().st_size > max_size:
             raise ToolError(tool_name="read_file_tool", message=f"File '{path}' is too large (>{max_size} bytes).")

        content = target_path.read_text(encoding='utf-8')
        return content
    except Exception as e:
        print(f"Error in read_file_tool: {e}")
        raise ToolError(tool_name="read_file_tool", message=f"Failed to read file '{path}'. Ensure path is valid and within the sandbox.")

@tool("Writes content to a text file within the sandbox, potentially overwriting.")
async def write_file_tool(path: str, content: str) -> str:
    """
    Writes the given content to a specified text file located relative to the Maity
    sandbox directory. Creates the file if it doesn't exist, overwrites if it does.
    Requires confirmation if enabled.

    Args:
        path: The relative path to the file within the sandbox (e.g., 'output.txt').
        content: The string content to write to the file.

    Returns:
        A confirmation message on success, or an error message.
    """
    print(f"Executing write_file_tool for path: {path}")
    if config.REQUIRE_CONFIRMATION_LOCAL:
        if not _needs_confirmation(f"write file '{path}'"):
            raise ToolError(tool_name="write_file_tool", message="Action denied by user confirmation requirement.")

    try:
        target_path = _resolve_sandbox_path(path)

        # Create parent directories if they don't exist
        target_path.parent.mkdir(parents=True, exist_ok=True)

        target_path.write_text(content, encoding='utf-8')
        return f"Successfully wrote content to '{path}'."
    except Exception as e:
        print(f"Error in write_file_tool: {e}")
        raise ToolError(tool_name="write_file_tool", message=f"Failed to write file '{path}'. Ensure path is valid and within the sandbox.")

@tool("Executes a code snippet (e.g., Python, Shell) in a sandboxed environment.")
async def execute_code_tool(code: str, language: str = "python") -> str:
    """
    Executes a given code snippet in a specified language (currently supports 'python'
    and 'shell'/'bash'). The execution is sandboxed. Requires confirmation if enabled.
    Returns the standard output and standard error.

    Args:
        code: The code snippet to execute.
        language: The language of the code ('python', 'shell', 'bash'). Defaults to 'python'.

    Returns:
        A string containing the stdout and stderr from the execution, or an error message.
    """
    print(f"Executing execute_code_tool for language: {language}")
    if config.REQUIRE_CONFIRMATION_LOCAL:
         if not _needs_confirmation(f"execute {language} code"):
             raise ToolError(tool_name="execute_code_tool", message="Action denied by user confirmation requirement.")

    if language not in ["python", "shell", "bash"]:
        raise ToolError(tool_name="execute_code_tool", message=f"Unsupported language: {language}. Only 'python' and 'shell'/'bash' are supported.")

    # --- DANGER ZONE: Execution ---
    # This needs *heavy* sandboxing. Running subprocess directly is risky.
    # Ideally, use Docker containers or a more secure execution environment.
    # The following is a basic, *INSECURE* example. DO NOT USE IN PRODUCTION AS IS.
    sandbox_dir = Path(config.LOCAL_SANDBOX_DIR).resolve()
    result = None
    timeout_seconds = 30 # Set a timeout

    try:
        if language == "python":
            # Write code to a temporary file within the sandbox to execute
            script_path = sandbox_dir / "temp_script.py"
            script_path.write_text(code, encoding='utf-8')
            # Execute using python interpreter, limit permissions, cwd to sandbox
            process = await asyncio.create_subprocess_exec(
                'python', str(script_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(sandbox_dir) # Run within sandbox
                # Consider adding user/group restrictions if possible on the OS
            )
        elif language in ["shell", "bash"]:
            # Safer to write to a script file than use shell=True
            script_path = sandbox_dir / "temp_script.sh"
            script_path.write_text(code, encoding='utf-8')
            # Make executable
            os.chmod(script_path, 0o755)
            # Execute the script
            process = await asyncio.create_subprocess_exec(
                str(script_path), # Execute the script directly
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(sandbox_dir)
            )

        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
        return_code = process.returncode

        # Clean up script file
        if 'script_path' in locals() and script_path.exists():
             script_path.unlink()

        result = f"Exit Code: {return_code}\n--- STDOUT ---\n{stdout.decode('utf-8', errors='replace')}\n--- STDERR ---\n{stderr.decode('utf-8', errors='replace')}"

    except asyncio.TimeoutError:
        process.kill() # Ensure process is killed on timeout
        result = f"Execution timed out after {timeout_seconds} seconds."
        # Clean up script file if needed
        if 'script_path' in locals() and script_path.exists():
             script_path.unlink()
    except Exception as e:
        print(f"Error in execute_code_tool: {e}")
        # Clean up script file if needed
        if 'script_path' in locals() and script_path.exists():
             script_path.unlink()
        raise ToolError(tool_name="execute_code_tool", message=f"Failed to execute code: {e}")

    return result

# Deprecate? execute_code_tool with language='shell' is safer.
@tool("Runs a single shell command in the sandboxed environment.")
async def run_shell_command_tool(command: str) -> str:
    """
    DEPRECATED - Use execute_code_tool(language='shell') instead for better control.
    Runs a single shell command directly. Highly risky. Use with extreme caution.
    Requires confirmation if enabled.

    Args:
        command: The shell command to run.

    Returns:
        A string containing the stdout and stderr, or an error message.
    """
    print(f"WARNING: Executing DANGEROUS run_shell_command_tool: {command}")
    if config.REQUIRE_CONFIRMATION_LOCAL:
         if not _needs_confirmation(f"run shell command: {command[:50]}..."):
             raise ToolError(tool_name="run_shell_command_tool", message="Action denied by user confirmation requirement.")

    # --- DANGER ZONE ---
    # Avoid shell=True. Split the command safely if possible.
    # If complex commands are needed, use execute_code_tool(language='shell').
    try:
        # Basic split (doesn't handle quotes well - prefer execute_code_tool)
        cmd_parts = command.split()
        sandbox_dir = Path(config.LOCAL_SANDBOX_DIR).resolve()
        timeout_seconds = 15

        process = await asyncio.create_subprocess_exec(
            *cmd_parts, # Pass parts directly
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(sandbox_dir)
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
        return_code = process.returncode
        return f"Exit Code: {return_code}\n--- STDOUT ---\n{stdout.decode('utf-8', errors='replace')}\n--- STDERR ---\n{stderr.decode('utf-8', errors='replace')}"

    except asyncio.TimeoutError:
         process.kill()
         return f"Command timed out after {timeout_seconds} seconds."
    except FileNotFoundError:
        raise ToolError(tool_name="run_shell_command_tool", message=f"Command not found: '{cmd_parts[0]}'. Ensure it's available in the environment.")
    except Exception as e:
        print(f"Error in run_shell_command_tool: {e}")
        raise ToolError(tool_name="run_shell_command_tool", message=f"Failed to run command '{command}': {e}")
