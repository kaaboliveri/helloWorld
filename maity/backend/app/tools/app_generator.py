# Ensure these imports are present at the top of app_generator.py
import os
import asyncio
import uuid
import zipfile
import json
from pathlib import Path
from typing import Optional, List, Dict, Any, DefaultDict # Added DefaultDict
from collections import defaultdict # Added defaultdict

from fastapi import WebSocket # Ensure WebSocket is imported if used by _send_status_update directly

from openai_agents.tool import tool, ToolError
from .. import config
from ..llm_clients import direct_llm_call, ModelType, get_model_configuration
# IMPORTANT: Import execute_code_tool for this step
from .local_system import execute_code_tool

_generated_apps: Dict[str, Dict[str, Any]] = {}
active_appgen_websockets: DefaultDict[str, List[WebSocket]] = defaultdict(list)


async def _send_status_update(project_id: str, status: str, message: Optional[str] = None, **kwargs: Any) -> None:
    # Existing in-memory update for _generated_apps
    print(f"APP_GEN_STATUS [{project_id}]: Status={status}, Msg={message}, Details={kwargs}")
    if project_id in _generated_apps:
        current_app_state = _generated_apps[project_id]
        current_app_state['status'] = status
        if message:
            current_app_state['message'] = message

        current_logs = current_app_state.get('logs', [])
        if not isinstance(current_logs, list): current_logs = []
        new_logs = kwargs.pop('logs', None)
        if new_logs:
            if isinstance(new_logs, list): current_logs.extend(new_logs)
            else: current_logs.append(str(new_logs))
        current_app_state['logs'] = current_logs

        current_app_state.update(kwargs)
    else: # Should ideally not happen if initialized in generate_app_tool
        _generated_apps[project_id] = {"status": status, "message": message, "logs": [], **kwargs}


    # WebSocket Sending Logic
    ws_payload = {
        "type": "appgen_status", # Consistent type for client parsing
        "project_id": project_id,
        "status": status,
        "message": message,
        **kwargs # Pass all other keyword arguments
    }
    # Ensure plan is sent only once and if available, not with every small update
    if status == "PLAN_COMPLETE" and 'plan' not in ws_payload:
         ws_payload['plan'] = _generated_apps.get(project_id, {}).get('plan')

    # Avoid sending full plan with every message after PLAN_COMPLETE
    if status != "PLAN_COMPLETE" and 'plan' in ws_payload:
        del ws_payload['plan']


    connections_to_remove = []
    if project_id in active_appgen_websockets:
        for ws_conn in active_appgen_websockets[project_id]:
            try:
                await ws_conn.send_json(ws_payload)
            except Exception as e:
                print(f"Error sending status to WebSocket for {project_id}: {e}. Marking for removal.")
                connections_to_remove.append(ws_conn)

        for ws_conn_to_remove in connections_to_remove:
            if ws_conn_to_remove in active_appgen_websockets[project_id]:
                active_appgen_websockets[project_id].remove(ws_conn_to_remove)

        if not active_appgen_websockets[project_id]:
            del active_appgen_websockets[project_id]

def _create_project_structure(project_path: Path, file_structure: Dict[str, Any]) -> None:
    abs_project_path = project_path.resolve()
    for item_name, content in file_structure.items():
        current_item_path = (abs_project_path / item_name).resolve()
        if abs_project_path not in current_item_path.parents and current_item_path != abs_project_path:
            print(f"Security Alert: Attempt to create file/dir '{current_item_path}' outside project path '{abs_project_path}'")
            continue
        if item_name.endswith('/'):
            current_item_path.mkdir(parents=True, exist_ok=True)
            if isinstance(content, dict) and content:
                 _create_project_structure(current_item_path, content)
        elif content is None or isinstance(content, str):
            current_item_path.parent.mkdir(parents=True, exist_ok=True)
            current_item_path.touch()
            if isinstance(content, str) and content:
                current_item_path.write_text(content, encoding='utf-8')
        else:
            print(f"Warning: Unknown item type for '{item_name}' in file structure: {content}")

@tool("Generates a full-stack web application based on a user prompt.")
async def generate_app_tool(prompt: str) -> str:
    project_id = str(uuid.uuid4())[:8]
    base_sandbox_path = Path(config.LOCAL_SANDBOX_DIR).resolve()
    project_path = (base_sandbox_path / f"appgen_{project_id}").resolve()
    if base_sandbox_path not in project_path.parents and project_path != base_sandbox_path:
        # Log to a temporary structure if _generated_apps doesn't have project_id yet
        # This case should ideally be rare as _generated_apps is initialized right after
        _generated_apps[project_id] = {"status": "ERROR", "error": "Failed to create secure project directory.", "logs": ["Failed to create secure project directory."]}
        raise ToolError("generate_app_tool", "Failed to create secure project directory.")
    project_path.mkdir(parents=True, exist_ok=True)
    _generated_apps[project_id] = {
        "status": "INITIALIZING", "prompt": prompt, "path": str(project_path),
        "plan": None, "files": {}, "logs": ["Initialization successful."], "preview_url": None, "error": None,
        "message": "Initializing app generation..."
    }
    asyncio.create_task(run_app_generation_flow(project_id, prompt, project_path))
    return f"App generation started with Project ID: {project_id}. Path: {project_path}."

def _get_all_filepaths_from_plan(file_structure: Dict[str, Any], current_path: Path = Path(".")) -> List[Path]:
    paths = []
    for name, content in file_structure.items():
        new_path = current_path / name
        if name.endswith('/'):
            if isinstance(content, dict) and content:
                paths.extend(_get_all_filepaths_from_plan(content, new_path))
        else:
            paths.append(new_path)
    return paths

async def run_app_generation_flow(project_id: str, prompt: str, project_path: Path) -> None:
    if project_id not in _generated_apps: # Should not happen if generate_app_tool initializes it
        print(f"Critical Error: _generated_apps entry for {project_id} not found at start of run_app_generation_flow.")
        return
    if not isinstance(_generated_apps[project_id].get('logs'), list):
        _generated_apps[project_id]['logs'] = []

    try:
        # --- Planning Phase ---
        await _send_status_update(project_id, "PLANNING", "Analyzing prompt and planning project structure...")
        # Conceptual Error Handling for Planning:
        # - If LLM call for planning fails, retry N times with backoff.
        # - If JSON parsing fails, could try to "clean" the raw_plan_response (e.g., extract from markdown)
        #   or ask LLM to reformat its last response strictly as JSON.
        # - If plan validation fails, could ask LLM to regenerate the plan adhering to the schema.
        planning_model_id = ModelType.CLAUDE_37_SONNET.value
        planning_prompt_content = f"""You are an expert software architect. Based on the user prompt: "{prompt}"
Generate a detailed plan as a single JSON object. This JSON should include keys: "stack" (object with tech details like language, framework, database, and optionally 'default_port' as a number), "files" (nested object for file structure, dir keys end with '/', file values are null), "components_description" (string), and "data_models_description" (string).
The "files" structure should be comprehensive. Example: {{"backend/": {{"main.py": null}}, "frontend/": {{"src/": {{"App.js": null}}}}}}
Be thorough with the file list for the chosen stack.
""" # Simplified example in prompt for brevity
        llm_messages_planning = [{"role": "user", "content": planning_prompt_content}]
        model_config_planning = get_model_configuration(planning_model_id)
        raw_plan_response = await direct_llm_call(messages=llm_messages_planning, model_id=planning_model_id, **model_config_planning.get("default_params", {}))

        parsed_plan: Optional[Dict[str, Any]] = None
        try:
            parsed_plan = json.loads(raw_plan_response)
            if not all(k in parsed_plan for k in ["stack", "files"]) or not isinstance(parsed_plan.get("files"), dict):
                raise ValueError("Plan missing required keys or 'files' is not a dictionary.")
            _generated_apps[project_id]['plan'] = parsed_plan
            await _send_status_update(project_id, "PLAN_COMPLETE", "Project plan generated successfully.", plan=parsed_plan)
        except (json.JSONDecodeError, ValueError) as e:
            error_msg = f"Failed to parse/validate LLM plan. Error: {e}. Raw response prefix: {raw_plan_response[:500]}"
            await _send_status_update(project_id, "ERROR", message=error_msg, error_details=raw_plan_response)
            return

        # --- Structure Creation ---
        # Conceptual Error Handling for Structure Creation:
        # - Mostly relies on filesystem permissions. Errors here are likely critical.
        # - Log specific path and error. May need to halt.
        if not parsed_plan or not isinstance(parsed_plan.get("files"), dict):
            await _send_status_update(project_id, "ERROR", "Plan 'files' structure is invalid or missing after planning.")
            return
        await _send_status_update(project_id, "STRUCTURE_CREATION", "Creating project directories and empty files...")
        try:
            _create_project_structure(project_path, parsed_plan["files"])
            await _send_status_update(project_id, "STRUCTURE_COMPLETE", "Project structure created.")
        except Exception as e:
            error_msg = f"Failed to create project structure: {type(e).__name__} - {e}"
            await _send_status_update(project_id, "ERROR", message=error_msg, error_details=str(e))
            return

        # --- Code Generation Phase ---
        await _send_status_update(project_id, "CODE_GENERATION_START", "Starting code generation for each file...")
        all_files_to_generate = _get_all_filepaths_from_plan(parsed_plan["files"])
        if not all_files_to_generate:
            _generated_apps[project_id]['logs'].append("No files found in the plan to generate code for.")
            await _send_status_update(project_id, "CODE_GENERATION_SKIPPED", "No files were planned for code generation.")
        else:
            _generated_apps[project_id].update({'files_total': len(all_files_to_generate), 'files_completed': 0})
            codegen_model_id = ModelType.GEMINI_25_PRO.value
            for i, file_rel_path_obj in enumerate(all_files_to_generate):
                file_rel_path = str(file_rel_path_obj)
                file_abs_path = (project_path / file_rel_path).resolve()
                abs_project_path_resolved = project_path.resolve()
                if abs_project_path_resolved not in file_abs_path.parents and file_abs_path.parent != abs_project_path_resolved and file_abs_path != abs_project_path_resolved:
                    _generated_apps[project_id]['files'][file_rel_path] = "Error: Security path violation."
                    _generated_apps[project_id]['logs'].append(f"Skipped file (security): {file_rel_path}")
                    continue

            # Conceptual Error Handling for Individual File Generation:
            # 1. Retry Strategy:
            #    - Implement a retry loop (e.g., 2-3 attempts per file).
            #    - On failure, log the error from the LLM or file writing.
            # 2. Prompt Variation for Retries:
            #    - First retry: Use the exact same prompt.
            #    - Second retry: Modify prompt, e.g., "The previous attempt to generate {file_rel_path} failed.
            #      Please ensure the output is only raw code. The error was: {previous_error_snippet}. Try again."
            #    - Or, if error suggests code was too long: "Please regenerate {file_rel_path} but be more concise."
            # 3. Critical File Failure vs. Non-Critical:
            #    - Define a list of "critical" files (e.g., main entry points, package.json, requirements.txt).
            #    - If a critical file fails all retries, the entire app generation might be marked as "FAILED".
            #    - If a non-critical file fails (e.g., a specific component, a test file), mark it as failed,
            #      log the error, and continue with other files. The app might be partially functional.
            # 4. LLM Self-Correction (Advanced):
            #    - Feed the erroneous generated code + error message back to the LLM and ask it to debug/fix its own code.

                await _send_status_update(project_id, "CODE_GENERATING_FILE",
                                          message=f"Generating: {file_rel_path} ({i+1}/{len(all_files_to_generate)})",
                                          current_file=file_rel_path, files_completed=i, files_total=len(all_files_to_generate))
                # ... (codegen_prompt setup and LLM call as before) ...
                # Simplified codegen LLM call for this example. Previous detailed prompt should be used.
                codegen_prompt = f"Generate code for {file_rel_path} given stack: {parsed_plan.get('stack')} and project context: {parsed_plan.get('components_description')}"
                try:
                # ... (existing codegen_prompt construction) ...
                # ... (existing LLM call for file_content) ...
                # ... (existing cleaning of file_content) ...
                # ... (existing file_abs_path.write_text(...)) ...
                # ... (existing success status update) ...
                    file_content = await direct_llm_call(messages=[{"role": "user", "content": codegen_prompt}], model_id=codegen_model_id, **get_model_configuration(codegen_model_id).get("default_params", {}))
                    file_abs_path.write_text(file_content.strip(), encoding='utf-8')
                    _generated_apps[project_id]['files'][file_rel_path] = "Generated"
                    _generated_apps[project_id]['files_completed'] = i + 1
                    await _send_status_update(project_id, "CODE_GENERATION_FILE_COMPLETE", message=f"Generated: {file_rel_path}", current_file=file_rel_path, files_completed=i+1)
                except Exception as gen_error:
                # ... (existing error logging and status update for this file) ...
                # Current: logs error and continues. Future: Implement retry/critical file logic here.
                    _generated_apps[project_id]['files'][file_rel_path] = f"Error: {type(gen_error).__name__}"
                    _generated_apps[project_id]['logs'].append(f"Error generating {file_rel_path}: {type(gen_error).__name__}")
                _generated_apps[project_id]['logs'].append(f"Conceptual: File {file_rel_path} failed. Retry logic would go here.")
                    await _send_status_update(project_id, "ERROR", message=f"Failed on {file_rel_path}", current_file=file_rel_path, error_details=str(gen_error)[:100])
                # If retries exhausted or critical file:
                # await _send_status_update(project_id, "FATAL_ERROR", f"Critical file {file_rel_path} failed generation. Aborting.")
                # return # Stop the entire process

        await _send_status_update(project_id, "CODE_GENERATION_ALL_FILES_ATTEMPTED", "Code generation finished.")

        # --- Execution Phase ---
        await _send_status_update(project_id, "EXECUTION_START", "Starting execution phase...")
        current_logs = _generated_apps[project_id].get('logs', [])
        current_logs.append("--- Execution Phase ---")
        _generated_apps[project_id]['logs'] = current_logs

        # Conceptual Error Handling for Installation Commands:
        # 1. Retry on Transient Errors:
        #    - If `execute_code_tool` output suggests a network issue for `pip install` or `npm install`,
        #      a brief delay and retry might resolve it.
        # 2. Parse Specific Errors:
        #    - For `pip install`: Look for "Could not find a version that satisfies the requirement", "No matching distribution found".
        #      This might indicate an issue in `requirements.txt`. Could potentially try to ask LLM to fix `requirements.txt`.
        #    - For `npm install`: Look for "404 Not Found" for a package, or peer dependency conflicts.
        #      LLM might be able to suggest fixes to `package.json`.
        # 3. Fallback/Skip:
        #    - If an install command fails after retries, halt the execution phase. The app likely won't run.

        install_commands = []
        run_command = None
        # Get default port from plan's stack or default to 8080
        # Ensure stack and default_port exist gracefully
        stack_info = parsed_plan.get("stack", {})
        app_port = stack_info.get("default_port")
        try:
            app_port = int(app_port) if app_port is not None else 8080
        except ValueError:
            app_port = 8080 # Fallback if parsing fails
            _generated_apps[project_id]['logs'].append(f"Warning: Could not parse 'default_port' from plan stack ('{stack_info.get('default_port')}'). Defaulting to {app_port}.")


        # Determine install and run commands
        package_json_path = project_path / "package.json"
        requirements_txt_path = project_path / "requirements.txt"

        if package_json_path.exists():
            install_commands.append("npm install")
            try:
                with open(package_json_path, 'r', encoding='utf-8') as f:
                    pkg_json = json.load(f)
                scripts = pkg_json.get("scripts", {})
                if "start" in scripts:
                    run_command = "npm start"
                elif "dev" in scripts:
                    run_command = "npm run dev"
                else: # Fallback if no common script, try generic node server if main file exists
                    main_js_options = ["server.js", "index.js", "app.js", "main.js"]
                    for js_file in main_js_options:
                        if (project_path / js_file).exists():
                            run_command = f"node {js_file}"
                            break
                if run_command and app_port != 8080: # Heuristic: try to append port if not default and using dev script
                    if "npm run dev" in run_command or "next dev" in run_command: # Common Next.js / Vite
                         run_command += f" -- --port {app_port}"
                    # Other frameworks might use PORT= env var, which is harder to inject here simply
            except Exception as e:
                _generated_apps[project_id]['logs'].append(f"Warning: Could not parse package.json to find run command: {e}")
                # Keep any previously inferred run_command or let it be None

        elif requirements_txt_path.exists(): # Check this only if package.json didn't determine a NodeJS project
            install_commands.append("pip install -r requirements.txt")
            # Prioritized check for main.py location
            main_py_locations = {
                "backend.main:app": project_path / "backend" / "main.py",
                "app.main:app": project_path / "app" / "main.py",
                "main:app": project_path / "main.py"
            }
            found_main_module = None
            for module_path_str, abs_path_to_check in main_py_locations.items():
                if abs_path_to_check.exists():
                    found_main_module = module_path_str
                    break

            if found_main_module:
                run_command = f"uvicorn {found_main_module} --host 0.0.0.0 --port {app_port}"
            else:
                 _generated_apps[project_id]['logs'].append("requirements.txt found, but no common main.py (main:app, app.main:app, backend.main:app) found for uvicorn.")


        if not install_commands and not run_command:
            _generated_apps[project_id]['logs'].append("Skipping execution: No standard dependency or run files (requirements.txt, package.json) found, or could not determine run command.")
            await _send_status_update(project_id, "EXECUTION_SKIPPED", "Could not determine installation or run commands.")
            return

        # Execute Install Commands (copied from previous, ensure it's robust)
        for cmd in install_commands:
            install_timeout = 180 # Longer timeout for installations (3 minutes)
            await _send_status_update(project_id, "EXECUTION_INSTALLING", f"Running: {cmd} (timeout: {install_timeout}s)")
            _generated_apps[project_id]['logs'].append(f"$ {cmd}")
            try:
                install_output_str = await execute_code_tool(code=cmd, language="shell", timeout_seconds=install_timeout)

                # Parse output for structured logging/status
                exit_code_str = install_output_str.split("Exit Code: ")[1].split('\n')[0] if "Exit Code: " in install_output_str else "N/A"
                stdout_content = install_output_str.split("--- STDOUT ---", 1)[1].split("--- STDERR ---", 1)[0].strip() if "--- STDOUT ---" in install_output_str else "N/A"
                stderr_content = install_output_str.split("--- STDERR ---", 1)[1].strip() if "--- STDERR ---" in install_output_str else "N/A"

                _generated_apps[project_id]['logs'].append(f"Exit Code: {exit_code_str}")
                if stdout_content and stdout_content != "(empty)": _generated_apps[project_id]['logs'].append(f"STDOUT:\n{stdout_content}")
                if stderr_content and stderr_content != "(empty)": _generated_apps[project_id]['logs'].append(f"STDERR:\n{stderr_content}")

                exec_details = {"command": cmd, "exit_code": exit_code_str, "stdout": stdout_content, "stderr": stderr_content}

                if exit_code_str != "0" and not ("already satisfied" in stdout_content or "updated" in stdout_content or "added" in stdout_content or "found" in stdout_content): # Refined check
                    raise ToolError("execute_code_tool", f"Install cmd '{cmd}' failed. Exit Code: {exit_code_str}. Stderr (first 100): {stderr_content[:100]}")

                await _send_status_update(project_id, "EXECUTION_INSTALL_COMPLETE", f"Install '{cmd}' finished.", exec_details=exec_details)
            except ToolError as e:
                _generated_apps[project_id]['logs'].append(f"Installation error: {e.message}")
                _generated_apps[project_id]['logs'].append(f"Conceptual: Install command '{cmd}' failed. LLM debugging could be attempted.")
                await _send_status_update(project_id, "ERROR", f"Installation failed: {cmd}. Error: {e.message}", exec_details={"command": cmd, "error": e.message})
                # await _send_status_update(project_id, "ERROR", f"Installation failed: {cmd}. LLM could try to fix dependencies.", ...)
                return

        # Conceptual Error Handling for Run Command:
        # 1. Analyze Stderr:
        #    - If `execute_code_tool` (for the short run check) returns stderr, analyze it for common issues:
        #        - "Port already in use": Could try to increment `app_port` and regenerate relevant config / re-run. (Complex)
        #        - "ModuleNotFoundError" / "cannot find module": Suggests an issue with imports or generated structure. LLM might fix.
        #        - Other framework-specific startup errors.
        # 2. Alternative Run Commands:
        #    - If the primary inferred `run_command` fails (e.g., `npm run dev`), try a fallback if known (e.g., `npm start`).
        # 3. User Feedback Loop (Future - Advanced):
        #    - If automated attempts fail: "App generated but failed to start with error: {stderr}. Would you like me to try X, Y, or Z?"

        # Attempt to Run the Application (Simulated/Short-lived)
        if run_command:
            run_app_timeout = 15 # Shorter timeout for app start check (15 seconds)
            await _send_status_update(project_id, "EXECUTION_RUNNING_APP", f"Attempting run: {run_command} (timeout: {run_app_timeout}s)")
            _generated_apps[project_id]['logs'].append(f"$ {run_command} (short run check)")
            try:
                run_output_str = await execute_code_tool(code=run_command, language="shell", timeout_seconds=run_app_timeout)

                exit_code_str = run_output_str.split("Exit Code: ")[1].split('\n')[0] if "Exit Code: " in run_output_str else "N/A"
                stdout_content = run_output_str.split("--- STDOUT ---", 1)[1].split("--- STDERR ---", 1)[0].strip() if "--- STDOUT ---" in run_output_str else "N/A"
                stderr_content = run_output_str.split("--- STDERR ---", 1)[1].strip() if "--- STDERR ---" in run_output_str else "N/A"

                _generated_apps[project_id]['logs'].append(f"Exit Code: {exit_code_str}")
                if stdout_content and stdout_content != "(empty)": _generated_apps[project_id]['logs'].append(f"STDOUT:\n{stdout_content}")
                if stderr_content and stderr_content != "(empty)": _generated_apps[project_id]['logs'].append(f"STDERR:\n{stderr_content}")

                exec_details = {"command": run_command, "exit_code": exit_code_str, "stdout": stdout_content, "stderr": stderr_content}
                preview_url_val = f"http://localhost:{app_port}" # Construct hypothetical URL

                if "timed out" in run_output_str.lower(): # Expected for servers
                    await _send_status_update(project_id, "EXECUTION_APP_RUN_SIMULATED",
                                              f"App started (simulated by timeout of: {run_command}).",
                                              preview_url=preview_url_val, exec_details=exec_details)
                    _generated_apps[project_id]['preview_url'] = preview_url_val
                elif "error" in stderr_content.lower() or (exit_code_str != "0" and exit_code_str != "N/A"): # Check stderr for errors too
                     raise ToolError("execute_code_tool", f"App '{run_command}' failed on startup. Exit: {exit_code_str}. Stderr: {stderr_content[:100]}")
                else:
                     await _send_status_update(project_id, "EXECUTION_APP_RUN_CHECKED",
                                              f"App command '{run_command}' executed. Output suggests it might have run briefly or is not a long-running server.",
                                              preview_url=preview_url_val, exec_details=exec_details)
                     _generated_apps[project_id]['preview_url'] = preview_url_val
            except ToolError as e:
                _generated_apps[project_id]['logs'].append(f"App run error: {e.message}")
                await _send_status_update(project_id, "ERROR", f"Failed to run app '{run_command}'. Error: {e.message}", exec_details={"command": run_command, "error": e.message})
                # await _send_status_update(project_id, "ERROR", f"App run failed: {run_command}. LLM could try to debug.", ...)
                return
        else:
            await _send_status_update(project_id, "EXECUTION_NO_RUN_COMMAND", "No run command identified.")

        await _send_status_update(project_id, "EXECUTION_PHASE_COMPLETE", "Execution phase finished.")

    # ... (outer try-except for the whole flow) ...
    except ToolError as e:
        error_msg = f"Tool error in app gen: {e.message}"
        await _send_status_update(project_id, "ERROR", message=error_msg, error_details=str(e))
        if project_id in _generated_apps: _generated_apps[project_id]['error'] = error_msg
    except Exception as e: # General catch-all
        # ... (existing general error handling) ...
        error_msg = f"Unexpected error in app gen: {type(e).__name__} - {e}"
        _generated_apps[project_id]['logs'].append(f"Conceptual: Unhandled exception in flow. Details: {type(e).__name__} - {e}")
        await _send_status_update(project_id, "ERROR", message=error_msg, error_details=str(e))
        if project_id in _generated_apps: _generated_apps[project_id]['error'] = error_msg
