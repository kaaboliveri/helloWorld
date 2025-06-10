import os
import asyncio
import uuid
import zipfile # Keep for future export functionality
import json # Import json for parsing
from pathlib import Path
from typing import Optional # Ensure Optional is imported

from openai_agents.tool import tool, ToolError
from .. import config
from ..llm_clients import direct_llm_call, ModelType, get_model_configuration

# Assuming execute_code_tool is still needed for later phases, ensure it's properly imported if used in this file.
# For this task, we are focusing on the planning phase which doesn't directly use execute_code_tool.
# from .local_system import execute_code_tool

_generated_apps = {}

async def _send_status_update(project_id: str, status: str, message: Optional[str] = None, **kwargs):
    print(f"APP_GEN [{project_id}]: Status={status}, Msg={message}, Details={kwargs}")
    if project_id in _generated_apps:
        _generated_apps[project_id]['status'] = status
        if message: _generated_apps[project_id]['message'] = message
        _generated_apps[project_id].update(kwargs) # Store any additional details like 'plan'
    # TODO: Send update via WebSocket to frontend

def _create_project_structure(project_path: Path, file_structure: dict):
    # Ensure project_path is absolute for reliable comparison
    abs_project_path = project_path.resolve()

    for item_name, content in file_structure.items():
        # Construct the full path for the current item
        current_item_path = (abs_project_path / item_name).resolve()

        # Security check: Ensure the resolved path of the item is within the project directory
        if abs_project_path not in current_item_path.parents and current_item_path != abs_project_path:
            print(f"Security Alert: Attempt to create file/dir '{current_item_path}' outside project path '{abs_project_path}'")
            continue # Skip this item

        if item_name.endswith('/'): # It's a directory based on key naming convention
            current_item_path.mkdir(parents=True, exist_ok=True)
            if isinstance(content, dict): # If it has nested structure
                _create_project_structure(current_item_path, content) # Recursive call with the current dir path
        elif content is None or isinstance(content, str): # It's a file
            current_item_path.parent.mkdir(parents=True, exist_ok=True) # Ensure parent dir exists
            current_item_path.touch() # Create empty file
            if isinstance(content, str) and content: # If content is a non-empty string, write it (for very simple placeholders)
                current_item_path.write_text(content, encoding='utf-8')
        else:
            print(f"Warning: Unknown item type or structure for '{item_name}' in file structure: {content}")


@tool("Generates a full-stack web application based on a user prompt.")
async def generate_app_tool(prompt: str) -> str:
    project_id = str(uuid.uuid4())[:8]
    # Ensure project_path is within LOCAL_SANDBOX_DIR and resolved
    base_sandbox_path = Path(config.LOCAL_SANDBOX_DIR).resolve()
    project_path = (base_sandbox_path / f"appgen_{project_id}").resolve()

    # Security: Double check project_path is within sandbox_dir after resolving
    if base_sandbox_path not in project_path.parents and project_path != base_sandbox_path:
        print(f"Security Alert: Resolved project_path '{project_path}' is outside sandbox '{base_sandbox_path}'. Aborting.")
        # Log this critical failure to the in-memory store if an entry was about to be made
        _generated_apps[project_id] = { # Temporary entry for error logging
            "status": "ERROR", "error": "Failed to create secure project directory.",
            "message": "Project path generation failed due to security constraints."
        }
        raise ToolError("generate_app_tool", "Failed to create secure project directory.")

    project_path.mkdir(parents=True, exist_ok=True)

    print(f"Starting app generation for prompt: '{prompt}' (ID: {project_id}, Path: {project_path})")
    _generated_apps[project_id] = {
        "status": "INITIALIZING",
        "prompt": prompt,
        "path": str(project_path),
        "plan": None,
        "files": {},
        "logs": [],
        "preview_url": None,
        "error": None,
        "message": "Initializing app generation..."
    }
    asyncio.create_task(run_app_generation_flow(project_id, prompt, project_path))
    return f"App generation started with Project ID: {project_id}. Path: {project_path}. Monitor status for updates."

async def run_app_generation_flow(project_id: str, prompt: str, project_path: Path):
    try:
        await _send_status_update(project_id, "PLANNING", "Analyzing prompt and planning project structure...")

        planning_model_id = ModelType.CLAUDE_37_SONNET.value
        planning_prompt_content = f"""
        You are an expert software architect. Based on the user prompt: "{prompt}"

        Generate a detailed plan for a full-stack web application. Your output MUST be a single JSON object.
        The JSON object should conform to the following structure:
        {{
          "stack": {{
            "backend_language": "e.g., Python, Node.js",
            "backend_framework": "e.g., FastAPI, Express",
            "frontend_language": "e.g., JavaScript, TypeScript",
            "frontend_framework": "e.g., React, Vue, Angular, Svelte",
            "database": "e.g., SQLite, PostgreSQL, MongoDB, None"
          }},
          "files": {{
            "path/to/file1.ext": null,
            "path/to/directory1/": {{
              "file2.ext": null,
              "file3.ext": null,
              "deeper_dir/": {{
                "file4.ext": null
              }}
            }},
            "README.md": null
          }},
          "components_description": "A brief (1-2 paragraphs) natural language description of the main components, features, and how they interact. Describe both backend and frontend parts.",
          "data_models_description": "A brief (1-2 paragraphs) natural language description of key data models or database schema if applicable. If no database, state that clearly."
        }}

        Guidelines for your response:
        1.  **Technology Stack (`stack`):** Be specific. For example, if Python, choose a framework like FastAPI or Flask. If Node.js, choose Express or NestJS.
        2.  **File Structure (`files`):**
            *   Represent directories by ending their keys with a forward slash (`/`).
            *   Nested directories and files should be represented as nested JSON objects.
            *   Use `null` as the value for files initially; their content will be generated later.
            *   Include common files like `package.json`, `requirements.txt`, `.gitignore`, Dockerfiles if appropriate for the stack.
        3.  **Components Description (`components_description`):** Describe the core logic, API endpoints for backend, and UI views/components for frontend.
        4.  **Data Models Description (`data_models_description`):** Describe primary entities, their attributes, and relationships. If no database, explicitly say so.
        5.  **JSON Output:** Ensure your entire response is a single, valid JSON object. Do not include any text before or after the JSON object. Do not use markdown code blocks (e.g., ```json) to wrap the JSON.

        Example for a simple To-Do app with Python/FastAPI backend and React frontend:
        {{
          "stack": {{
            "backend_language": "Python",
            "backend_framework": "FastAPI",
            "frontend_language": "JavaScript",
            "frontend_framework": "React",
            "database": "SQLite"
          }},
          "files": {{
            "backend/": {{
              "main.py": null,
              "models.py": null,
              "crud.py": null,
              "requirements.txt": null,
              "Dockerfile": null
            }},
            "frontend/": {{
              "src/": {{
                "App.js": null,
                "components/": {{
                  "TodoList.js": null,
                  "TodoItem.js": null
                }},
                "index.js": null
              }},
              "public/": {{ "index.html": null }},
              "package.json": null,
              "Dockerfile": null
            }},
            ".gitignore": null,
            "docker-compose.yml": null,
            "README.md": null
          }},
          "components_description": "Backend: FastAPI app with endpoints for CRUD operations on to-do items (/todos). Handles SQLite database interaction. Frontend: React app with components for displaying to-do list, individual items, and an input form. Communicates with backend API.",
          "data_models_description": "A 'Todo' model with 'id' (integer, primary key), 'text' (string), and 'completed' (boolean) attributes. Stored in an SQLite database table."
        }}
        """

        llm_messages = [{"role": "user", "content": planning_prompt_content}]
        model_config = get_model_configuration(planning_model_id)
        llm_params = model_config.get("default_params", {})

        raw_plan_response = await direct_llm_call(
            messages=llm_messages,
            model_id=planning_model_id,
            **llm_params
        )

        parsed_plan = None
        try:
            # Attempt to parse the entire response as JSON directly
            # The prompt now strictly asks for JSON only.
            parsed_plan = json.loads(raw_plan_response)

            # Basic validation of the parsed plan structure
            required_keys = ["stack", "files", "components_description", "data_models_description"]
            if not all(key in parsed_plan for key in required_keys):
                raise ValueError(f"LLM plan response is missing one or more required keys: {required_keys}")
            if not isinstance(parsed_plan.get("files"), dict) or not isinstance(parsed_plan.get("stack"), dict):
                 raise ValueError("'files' and 'stack' must be dictionaries in the plan.")


            _generated_apps[project_id]['plan'] = parsed_plan
            await _send_status_update(project_id, "PLAN_COMPLETE", "Project plan generated successfully.", plan=parsed_plan)
            print(f"Project plan for {project_id} successfully parsed and stored.")

        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse LLM plan response as JSON. Error: {e}. Raw response prefix: {raw_plan_response[:500]}"
            print(error_msg)
            await _send_status_update(project_id, "ERROR", error_msg, error_details=raw_plan_response)
            _generated_apps[project_id]['error'] = error_msg
            return
        except ValueError as e: # Catch our custom validation errors
            error_msg = f"LLM plan response validation failed: {e}. Raw response prefix: {raw_plan_response[:500]}"
            print(error_msg)
            await _send_status_update(project_id, "ERROR", error_msg, error_details=raw_plan_response)
            _generated_apps[project_id]['error'] = error_msg
            return

        # --- Structure Creation (moved here to use the parsed plan) ---
        if parsed_plan and 'files' in parsed_plan and isinstance(parsed_plan['files'], dict):
            await _send_status_update(project_id, "STRUCTURE_CREATION", "Creating project directories and files based on the plan...")
            try:
                _create_project_structure(project_path, parsed_plan.get("files", {}))
                await _send_status_update(project_id, "STRUCTURE_COMPLETE", "Project structure created.")
            except Exception as e:
                error_msg = f"Failed to create project structure: {type(e).__name__} - {e}"
                print(error_msg)
                await _send_status_update(project_id, "ERROR", error_msg)
                _generated_apps[project_id]['error'] = error_msg
                return # Stop if structure creation fails
        else:
            await _send_status_update(project_id, "WARNING", "No valid file structure (dictionary) found in the plan to create.")


        # --- Code Generation Phase (Placeholder for now) ---
        await _send_status_update(project_id, "CODE_GENERATION_PENDING", "Code generation will proceed based on the plan.")
        # ... (rest of the generation flow will be implemented in future steps) ...
        # For now, let's simulate completion for testing purposes or stop here.
        current_logs = _generated_apps[project_id].get('logs', [])
        current_logs.append("Planning complete. Structure created (if any). Code generation pending.")
        _generated_apps[project_id]['logs'] = current_logs
        await _send_status_update(project_id, "PLANNING_SUCCESSFUL_PENDING_CODEGEN", "Planning and structure creation complete. Ready for code generation.")


    except ToolError as e: # Catch ToolErrors from direct_llm_call or other tools if they were used
        print(f"ToolError during app generation flow for {project_id}: {e}")
        await _send_status_update(project_id, "ERROR", f"A tool error occurred: {e.message}", error_details=str(e))
        _generated_apps[project_id]['error'] = e.message
    except Exception as e:
        print(f"Unexpected error during app generation flow for {project_id}: {type(e).__name__} - {e}")
        await _send_status_update(project_id, "ERROR", f"An unexpected error occurred: {type(e).__name__} - {e}", error_details=str(e))
        _generated_apps[project_id]['error'] = str(e)

# (Keep _create_project_structure and generate_app_tool, but ensure _create_project_structure is robust)
