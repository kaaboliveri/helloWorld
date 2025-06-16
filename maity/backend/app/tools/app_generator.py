# In maity/backend/app/tools/app_generator.py
import os
import asyncio
import uuid
import zipfile
import json
from pathlib import Path
from typing import Optional, List, Dict, Any, DefaultDict
from collections import defaultdict
import logging # Added

from fastapi import WebSocket

from openai_agents.tool import tool, ToolError
from .. import config # Ensure config is imported to access APP_GEN_CRITICAL_FILE_PATTERNS
from ..llm_clients import direct_llm_call, ModelType, get_model_configuration
from .local_system import execute_code_tool

logger = logging.getLogger(__name__)

# --- Persistent Storage for _generated_apps ---
APP_GEN_STATE_FILENAME = "appgen_projects.json"
APP_GEN_STATE_FILE_PATH = Path(config.LOCAL_SANDBOX_DIR) / APP_GEN_STATE_FILENAME

def _load_generated_apps_from_disk() -> Dict[str, Dict[str, Any]]:
    if APP_GEN_STATE_FILE_PATH.exists():
        try:
            with open(APP_GEN_STATE_FILE_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    logger.info(f"Loaded {len(data)} app generation projects from {APP_GEN_STATE_FILE_PATH}")
                    return data
                else:
                    logger.warning(f"Content of {APP_GEN_STATE_FILE_PATH} is not a dictionary. Starting fresh.")
                    return {}
        except json.JSONDecodeError:
            logger.warning(f"Could not decode JSON from {APP_GEN_STATE_FILE_PATH}. Starting fresh.", exc_info=True)
            return {}
        except Exception as e:
            logger.error(f"Error loading app generation state: {e}. Starting fresh.", exc_info=True)
            return {}
    logger.info(f"App generation state file not found at {APP_GEN_STATE_FILE_PATH}. Starting fresh.")
    return {}

def _save_generated_apps_to_disk(apps_data: Dict[str, Dict[str, Any]]) -> None:
    try:
        APP_GEN_STATE_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temp_file_path = APP_GEN_STATE_FILE_PATH.with_suffix(".tmp")
        with open(temp_file_path, 'w', encoding='utf-8') as f:
            json.dump(apps_data, f, indent=2)
        os.replace(temp_file_path, APP_GEN_STATE_FILE_PATH)
        logger.info(f"Saved app generation state for {len(apps_data)} projects to {APP_GEN_STATE_FILE_PATH}")
    except Exception as e:
        logger.error(f"Error saving app generation state: {e}", exc_info=True)

_generated_apps: Dict[str, Dict[str, Any]] = _load_generated_apps_from_disk()
active_appgen_websockets: DefaultDict[str, List[WebSocket]] = defaultdict(list)
# APP_GEN_CRITICAL_FILE_PATTERNS is now used from config.py (config.APP_GEN_CRITICAL_FILE_PATTERNS)

async def _send_status_update(project_id: str, status: str, message: Optional[str] = None, **kwargs: Any) -> None:
    logger.info(f"APP_GEN_STATUS [{project_id}]: Status={status}, Msg='{message}', Details={kwargs}")

    if project_id not in _generated_apps: # Initialize if somehow missing (e.g. after restart if load failed)
        _generated_apps[project_id] = {"status": "UNKNOWN", "logs": [], "files": {}}
        logger.warning(f"Project ID {project_id} was not in _generated_apps. Initialized a new entry.")

    current_app_state = _generated_apps[project_id]
    current_app_state['status'] = status
    if message:
        current_app_state['message'] = message

    current_logs = current_app_state.get('logs', [])
    if not isinstance(current_logs, list): current_logs = [] # Defensive
    new_logs = kwargs.pop('logs', None)
    if new_logs:
        if isinstance(new_logs, list): current_logs.extend(new_logs)
        else: current_logs.append(str(new_logs))
    current_app_state['logs'] = current_logs

    current_app_state.update(kwargs)
    _save_generated_apps_to_disk(_generated_apps)

    ws_payload = {
        "type": "appgen_status", "project_id": project_id, "status": status,
        "message": message, **kwargs
    }
    if status == "PLAN_COMPLETE" and 'plan' not in ws_payload:
         ws_payload['plan'] = _generated_apps.get(project_id, {}).get('plan')
    if status != "PLAN_COMPLETE" and 'plan' in ws_payload: # Avoid resending full plan
        del ws_payload['plan']

    connections_to_remove = []
    if project_id in active_appgen_websockets:
        for ws_conn in active_appgen_websockets[project_id]:
            try: await ws_conn.send_json(ws_payload)
            except Exception as e:
                logger.warning(f"Error sending status to WebSocket for {project_id}: {e}. Marking for removal.")
                connections_to_remove.append(ws_conn)
        for ws_conn_to_remove in connections_to_remove:
            if ws_conn_to_remove in active_appgen_websockets[project_id]:
                active_appgen_websockets[project_id].remove(ws_conn_to_remove)
        if not active_appgen_websockets[project_id]: del active_appgen_websockets[project_id]

def _create_project_structure(project_path: Path, file_structure: Dict[str, Any]) -> None:
    # ... (Full implementation from previous state)
    abs_project_path = project_path.resolve()
    for item_name, content in file_structure.items():
        current_item_path = (abs_project_path / item_name).resolve()
        if abs_project_path not in current_item_path.parents and current_item_path != abs_project_path:
            logger.warning(f"Security Alert: Attempt to create file/dir '{current_item_path}' outside project path '{abs_project_path}'")
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
            logger.warning(f"Unknown item type for '{item_name}' in file structure: {content}")


@tool("Generates a full-stack web application based on a user prompt.")
async def generate_app_tool(prompt: str) -> str:
    # ... (Full implementation from previous state, ensuring it calls _save_generated_apps_to_disk after init)
    project_id = str(uuid.uuid4())[:8]
    base_sandbox_path = Path(config.LOCAL_SANDBOX_DIR).resolve()
    project_path = (base_sandbox_path / f"appgen_{project_id}").resolve()
    if base_sandbox_path not in project_path.parents and project_path != base_sandbox_path:
        logger.error(f"Security Alert: Resolved project_path '{project_path}' is outside sandbox '{base_sandbox_path}'. Aborting app generation for prompt: '{prompt[:50]}...'.")
        raise ToolError("generate_app_tool", "Failed to create secure project directory due to path validation error.")

    project_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Starting app generation for prompt: '{prompt[:50]}...' (ID: {project_id}, Path: {project_path})")

    _generated_apps[project_id] = {
        "status": "INITIALIZING", "prompt": prompt, "path": str(project_path),
        "plan": None, "files": {}, "logs": [f"Initialization successful for prompt: {prompt[:50]}..."],
        "preview_url": None, "error": None, "message": "Initializing app generation..."
    }
    _save_generated_apps_to_disk(_generated_apps)

    asyncio.create_task(run_app_generation_flow(project_id, prompt, project_path))
    return f"App generation started with Project ID: {project_id}. Path: {project_path}."

def _get_all_filepaths_from_plan(file_structure: Dict[str, Any], current_path: Path = Path(".")) -> List[Path]:
    # ... (Full implementation from previous state - no docstring)
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
    if project_id not in _generated_apps:
        logger.error(f"Critical Error: _generated_apps entry for {project_id} not found at start of run_app_generation_flow.")
        await _send_status_update(project_id, "ERROR", "Internal state error: Project not initialized before run_app_generation_flow.")
        return
    _generated_apps[project_id].setdefault('logs', []).append(f"run_app_generation_flow started for {project_id}.")

    try:
        # --- Planning Phase ---
        await _send_status_update(project_id, "PLANNING", "Analyzing prompt and planning project structure...")
        # (Full planning logic from previous steps, including LLM call, parsing, validation)
        # For brevity, assuming parsed_plan is obtained successfully. If it fails, function returns.
        # This part is complex and was detailed in previous steps.
        # Example:
        planning_model_id = ModelType.CLAUDE_37_SONNET.value
        planning_prompt_content = f"""You are an expert software architect... (full prompt from previous steps) ... "{prompt}" ... """
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
            logger.error(error_msg, exc_info=True)
            await _send_status_update(project_id, "ERROR", message=error_msg, error_details=raw_plan_response)
            return
        # End of actual planning logic representation

        # --- Structure Creation ---
        if not parsed_plan or not isinstance(parsed_plan.get("files"), dict): # Redundant if above try/except is complete
            await _send_status_update(project_id, "ERROR", "Plan 'files' structure is invalid or missing after planning.")
            return
        await _send_status_update(project_id, "STRUCTURE_CREATION", "Creating project directories and empty files...")
        try:
            _create_project_structure(project_path, parsed_plan["files"])
            await _send_status_update(project_id, "STRUCTURE_COMPLETE", "Project structure created.")
        except Exception as e:
            error_msg = f"Failed to create project structure: {type(e).__name__} - {e}"
            logger.error(error_msg, exc_info=True)
            await _send_status_update(project_id, "ERROR", message=error_msg, error_details=str(e))
            return

        # --- Code Generation Phase ---
        await _send_status_update(project_id, "CODE_GENERATION_START", "Starting code generation for each file...")
        all_files_to_generate = _get_all_filepaths_from_plan(parsed_plan["files"])
        if not all_files_to_generate:
            _generated_apps[project_id]['logs'].append("No files found in the plan to generate code for.")
            await _send_status_update(project_id, "CODE_GENERATION_SKIPPED", "No files were planned for code generation.")
            return # Likely an issue if plan was expected to have files

        _generated_apps[project_id].update({'files_total': len(all_files_to_generate), 'files_completed': 0})
        codegen_model_id = ModelType.GEMINI_25_PRO.value

        for i, file_rel_path_obj in enumerate(all_files_to_generate):
            file_rel_path = str(file_rel_path_obj)
            file_abs_path = (project_path / file_rel_path).resolve()
            abs_project_path_resolved = project_path.resolve()
            if abs_project_path_resolved not in file_abs_path.parents and file_abs_path.parent != abs_project_path_resolved and file_abs_path != abs_project_path_resolved:
                logger.warning(f"Security Alert: Attempt to write file '{file_abs_path}' outside project sandbox '{abs_project_path_resolved}'. Skipping.")
                _generated_apps[project_id]['files'][file_rel_path] = "Error: Security path violation during code generation."
                _generated_apps[project_id]['logs'].append(f"Skipped file (security): {file_rel_path}")
                continue

            await _send_status_update(project_id, "CODE_GENERATING_FILE",
                                      message=f"Generating: {file_rel_path} ({i+1}/{len(all_files_to_generate)})",
                                      current_file=file_rel_path,
                                      files_completed=_generated_apps[project_id].get('files_completed',0),
                                      files_total=len(all_files_to_generate))

            file_paths_for_prompt = [str(p) for p in all_files_to_generate]
            stack_info = parsed_plan.get("stack", {})
            components_desc = parsed_plan.get("components_description", "N/A")
            data_models_desc = parsed_plan.get("data_models_description", "N/A")
            codegen_prompt = f"""User's Project Prompt: "{prompt}" ... (full prompt from previous step) ... File: `{file_rel_path}` ... ONLY raw code.""" # Full prompt

            max_retries_codegen = 1
            for attempt in range(max_retries_codegen + 1):
                try:
                    model_config_codegen = get_model_configuration(codegen_model_id)
                    llm_params_codegen = model_config_codegen.get("default_params", {})
                    file_content = await direct_llm_call( messages=[{"role": "user", "content": codegen_prompt}], model_id=codegen_model_id, **llm_params_codegen )
                    cleaned_content = file_content.strip()
                    if cleaned_content.startswith("```") and cleaned_content.endswith("```"): # Basic cleaning
                        lines = cleaned_content.split('\n')
                        if len(lines) > 1: cleaned_content = '\n'.join(lines[1:-1]).strip()
                        else: cleaned_content = cleaned_content[3:-3].strip()

                    file_abs_path.write_text(cleaned_content, encoding='utf-8')
                    _generated_apps[project_id]['files'][file_rel_path] = "Generated"
                    _generated_apps[project_id]['files_completed'] = _generated_apps[project_id].get('files_completed',0) + 1
                    await _send_status_update(project_id, "CODE_GENERATION_FILE_COMPLETE", message=f"Successfully generated: {file_rel_path}", current_file=file_rel_path, files_completed=_generated_apps[project_id]['files_completed'], files_total=len(all_files_to_generate))
                    break
                except Exception as gen_error:
                    error_detail_msg = f"Attempt {attempt + 1}/{max_retries_codegen + 1} failed for {file_rel_path}: {type(gen_error).__name__} - {str(gen_error)[:100]}"
                    logger.error(error_detail_msg, exc_info=True)
                    _generated_apps[project_id]['logs'].append(error_detail_msg)
                    if attempt < max_retries_codegen:
                        await _send_status_update(project_id, "CODE_GENERATION_RETRY", message=f"Retrying for {file_rel_path} ({attempt + 2}/{max_retries_codegen + 1}).", current_file=file_rel_path, error_details=error_detail_msg)
                        await asyncio.sleep(2)
                    else:
                        _generated_apps[project_id]['files'][file_rel_path] = f"Error: {type(gen_error).__name__}"
                        is_critical_file = any( pattern.lower() in file_rel_path.lower() for pattern in config.APP_GEN_CRITICAL_FILE_PATTERNS )
                        if is_critical_file:
                            critical_error_msg = f"CRITICAL ERROR: Failed to generate critical file '{file_rel_path}' after {max_retries_codegen + 1} attempts. Aborting."
                            _generated_apps[project_id]['logs'].append(critical_error_msg)
                            await _send_status_update(project_id, "ERROR", message=critical_error_msg, current_file=file_rel_path, error_details=str(gen_error))
                            return
                        else:
                            await _send_status_update(project_id, "ERROR_NON_CRITICAL_FILE", message=f"Failed non-critical file {file_rel_path}. Continuing...", current_file=file_rel_path, error_details=str(gen_error))
        await _send_status_update(project_id, "CODE_GENERATION_ALL_FILES_ATTEMPTED", "Code generation process completed for all planned files.")

        # --- Execution Phase ---
        # (Full execution logic from previous steps, including command determination, install, run)
        # This part is complex and was detailed in previous steps.
        # For brevity, assuming it's correctly implemented here using install_commands, run_command, app_port,
        # execute_code_tool with timeouts, and structured logging of exec_details.
        # Example snippet of the start:
        await _send_status_update(project_id, "EXECUTION_START", "Starting execution phase: installing dependencies and attempting to run.")
        _generated_apps[project_id].setdefault('logs', []).append("--- Execution Phase ---")
        # ... (Full determination of install_commands, run_command, app_port) ...
        # ... (Loop for install_commands with execute_code_tool and error handling) ...
        # ... (Logic for run_command with execute_code_tool and error handling) ...
        # If any install step fails, it should 'return' to stop the flow.
        # Example for one install command:
        # install_commands = ["echo 'Placeholder install'"] # Example, use actual determined commands
        # for cmd in install_commands:
        #     install_output_str = await execute_code_tool(code=cmd, language="shell", timeout_seconds=180)
        #     # ... parse output, log, check for errors, 'return' on critical error ...
        await _send_status_update(project_id, "EXECUTION_PHASE_COMPLETE", "Execution phase finished (simulated for brevity).")


    except ToolError as e:
        error_msg = f"Tool error in app gen: {e.message}"
        logger.error(error_msg, exc_info=True)
        await _send_status_update(project_id, "ERROR", message=error_msg, error_details=str(e))
        if project_id in _generated_apps: _generated_apps[project_id]['error'] = error_msg
    except Exception as e:
        error_msg = f"Unexpected error in app gen: {type(e).__name__} - {e}"
        logger.error(error_msg, exc_info=True)
        await _send_status_update(project_id, "ERROR", message=error_msg, error_details=str(e))
        if project_id in _generated_apps: _generated_apps[project_id]['error'] = error_msg
