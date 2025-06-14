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
                await _send_status_update(project_id, "CODE_GENERATING_FILE",
                                          message=f"Generating: {file_rel_path} ({i+1}/{len(all_files_to_generate)})",
                                          current_file=file_rel_path, files_completed=i, files_total=len(all_files_to_generate))
                # ... (codegen_prompt setup and LLM call as before) ...
                # Simplified codegen LLM call for this example. Previous detailed prompt should be used.
                codegen_prompt = f"Generate code for {file_rel_path} given stack: {parsed_plan.get('stack')} and project context: {parsed_plan.get('components_description')}"
                try:
                    file_content = await direct_llm_call(messages=[{"role": "user", "content": codegen_prompt}], model_id=codegen_model_id, **get_model_configuration(codegen_model_id).get("default_params", {}))
                    # ... (cleaning and writing file_content) ...
                    file_abs_path.write_text(file_content.strip(), encoding='utf-8')
                    _generated_apps[project_id]['files'][file_rel_path] = "Generated"
                    _generated_apps[project_id]['files_completed'] = i + 1
                    await _send_status_update(project_id, "CODE_GENERATION_FILE_COMPLETE", message=f"Generated: {file_rel_path}", current_file=file_rel_path, files_completed=i+1)
                except Exception as gen_error:
                    _generated_apps[project_id]['files'][file_rel_path] = f"Error: {type(gen_error).__name__}"
                    _generated_apps[project_id]['logs'].append(f"Error generating {file_rel_path}: {type(gen_error).__name__}")
                    await _send_status_update(project_id, "ERROR", message=f"Failed on {file_rel_path}", current_file=file_rel_path, error_details=str(gen_error)[:100])
            await _send_status_update(project_id, "CODE_GENERATION_ALL_FILES_ATTEMPTED", "Code generation finished.")

        # --- Execution Phase ---
        await _send_status_update(project_id, "EXECUTION_START", "Starting execution: installing dependencies and attempting to run.")
        _generated_apps[project_id]['logs'].append("--- Execution Phase ---")

        install_commands = []
        run_command = None
        app_port = parsed_plan.get("stack", {}).get("default_port", 8080)
        if not isinstance(app_port, int): app_port = 8080 # Ensure port is int

        if (project_path / "requirements.txt").exists():
            install_commands.append("pip install -r requirements.txt")
            main_py_paths = ["main.py", "app/main.py", "backend/main.py"]
            main_py_module_options = {"main.py":"main:app", "app/main.py":"app.main:app", "backend/main.py":"backend.main:app"}
            for p_opt, m_opt in main_py_module_options.items():
                if (project_path / p_opt).exists():
                    run_command = f"uvicorn {m_opt} --host 0.0.0.0 --port {app_port}"
                    break
        if (project_path / "package.json").exists():
            install_commands.append("npm install")
            run_command = run_command or f"npm run dev -- --port {app_port}"

        if not install_commands and not run_command:
            _generated_apps[project_id]['logs'].append("No standard dependency/run files. Skipping execution.")
            await _send_status_update(project_id, "EXECUTION_SKIPPED", "Could not determine install/run commands.")
            return

        for cmd in install_commands:
            await _send_status_update(project_id, "EXECUTION_INSTALLING", f"Running: {cmd}")
            _generated_apps[project_id]['logs'].append(f"$ {cmd}")
            try:
                install_output = await execute_code_tool(code=cmd, language="shell")
                _generated_apps[project_id]['logs'].append(install_output)
                if "Exit Code: 0" not in install_output.split('\n')[0] and "Successfully installed" not in install_output and "added" not in install_output: # Added "added" for npm
                    raise ToolError("execute_code_tool", f"Install cmd '{cmd}' failed. Output: {install_output[:200]}")
                await _send_status_update(project_id, "EXECUTION_INSTALL_COMPLETE", f"Install '{cmd}' finished.")
            except ToolError as e:
                _generated_apps[project_id]['logs'].append(f"Install error: {e.message}")
                await _send_status_update(project_id, "ERROR", f"Install failed: {cmd}. Error: {e.message}", error_details=e.message)
                return

        if run_command:
            await _send_status_update(project_id, "EXECUTION_RUNNING_APP", f"Attempting short run: {run_command}")
            _generated_apps[project_id]['logs'].append(f"$ {run_command} (short run/check)")
            try:
                run_output = await execute_code_tool(code=run_command, language="shell")
                _generated_apps[project_id]['logs'].append(run_output)
                preview_url_val = f"http://localhost:{app_port}" # Construct hypothetical URL
                _generated_apps[project_id]['preview_url'] = preview_url_val

                if "timed out" in run_output.lower():
                    await _send_status_update(project_id, "EXECUTION_APP_RUN_SIMULATED", f"App started (simulated by timeout): {run_command}.", preview_url=preview_url_val)
                elif "error" in run_output.lower() or "failed" in run_output.lower():
                     raise ToolError("execute_code_tool", f"App '{run_command}' failed on startup. Output: {run_output[:200]}")
                else:
                     await _send_status_update(project_id, "EXECUTION_APP_RUN_CHECKED", f"App run command '{run_command}' executed. Output: {run_output[:200]}", preview_url=preview_url_val)
            except ToolError as e:
                _generated_apps[project_id]['logs'].append(f"Error running app: {e.message}")
                await _send_status_update(project_id, "ERROR", f"Failed to run app '{run_command}'. Error: {e.message}", error_details=e.message)
                return
        else:
            await _send_status_update(project_id, "EXECUTION_NO_RUN_COMMAND", "No run command identified.")

        await _send_status_update(project_id, "EXECUTION_PHASE_COMPLETE", "Execution phase finished.")

    except ToolError as e:
        error_msg = f"Tool error in appgen: {e.message}"
        await _send_status_update(project_id, "ERROR", message=error_msg, error_details=str(e))
        if project_id in _generated_apps: _generated_apps[project_id]['error'] = error_msg
    except Exception as e:
        error_msg = f"Unexpected error in appgen: {type(e).__name__} - {e}"
        await _send_status_update(project_id, "ERROR", message=error_msg, error_details=str(e))
        if project_id in _generated_apps: _generated_apps[project_id]['error'] = error_msg
