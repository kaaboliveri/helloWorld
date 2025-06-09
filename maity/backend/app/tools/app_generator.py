import os
import asyncio
import uuid
import zipfile
from pathlib import Path
from typing import Optional # Added this import
from openai_agents.tool import tool, ToolError
from .. import config
from ..llm_clients import direct_llm_call, ModelType # Use direct call for planning/generation
from .local_system import execute_code_tool # Use for install/run

# --- App Generation State Management (In-memory example) ---
# Needs persistent storage in a real application
_generated_apps = {} # Store state like { project_id: { status: "...", path: "...", ... } }

# --- Helper Functions ---
async def _send_status_update(project_id: str, status: str, message: Optional[str] = None, **kwargs):
    """ Placeholder for sending status updates (e.g., via WebSocket). """
    print(f"APP_GEN [{project_id}]: Status={status}, Msg={message}, Details={kwargs}")
    if project_id in _generated_apps:
        _generated_apps[project_id]['status'] = status
        _generated_apps[project_id]['message'] = message
        # TODO: Send update via WebSocket to frontend

def _create_project_structure(project_path: Path, file_structure: dict):
    """Creates directories and empty files based on the planned structure."""
    for item, content in file_structure.items():
        item_path = project_path / item
        if isinstance(content, dict): # It's a directory
            item_path.mkdir(parents=True, exist_ok=True)
            _create_project_structure(item_path, content)
        else: # It's a file path (content will be generated later)
            item_path.parent.mkdir(parents=True, exist_ok=True)
            item_path.touch() # Create empty file

# --- Tool Definition ---

@tool("Generates a full-stack web application based on a user prompt.")
async def generate_app_tool(prompt: str) -> str:
    """
    Initiates the process of generating a full-stack web application from a
    natural language prompt. It plans the structure, generates code file by file,
    attempts to install dependencies and run the app in a sandbox.
    The process runs asynchronously and provides status updates.

    Args:
        prompt: A detailed description of the desired web application.

    Returns:
        A confirmation message indicating the generation process has started,
        including a project ID for tracking. Use other tools or wait for
        updates to get the final status and preview URL.
    """
    project_id = str(uuid.uuid4())[:8]
    project_path = Path(config.LOCAL_SANDBOX_DIR) / f"appgen_{project_id}"
    project_path.mkdir(parents=True, exist_ok=True)

    print(f"Starting app generation for prompt: '{prompt}' (ID: {project_id})")

    # Store initial state
    _generated_apps[project_id] = {
        "status": "INITIALIZING",
        "prompt": prompt,
        "path": str(project_path),
        "plan": None,
        "files": {},
        "logs": [],
        "preview_url": None,
        "error": None
    }

    # Start the generation process in the background (don't block the agent tool call)
    asyncio.create_task(run_app_generation_flow(project_id, prompt, project_path))

    return f"App generation started with Project ID: {project_id}. Monitor status for updates."

# --- Asynchronous Generation Flow ---

async def run_app_generation_flow(project_id: str, prompt: str, project_path: Path):
    """The main asynchronous flow for generating the application."""
    try:
        await _send_status_update(project_id, "PLANNING", "Analyzing prompt and planning project structure...")

        # 1. Planning Phase (using a powerful LLM like Claude 3.7 or Gemini 2.5)
        planning_model = ModelType.CLAUDE_37_SONNET # Or Gemini 2.5 Pro
        planning_prompt = f"""
        Based on the user prompt: "{prompt}"

        Generate a detailed plan for a full-stack web application. Specify:
        1.  **Technology Stack:** (e.g., Backend: Python/FastAPI, Frontend: React/Vite, DB: SQLite)
        2.  **File Structure:** A hierarchical list of all necessary files and directories (e.g., `backend/main.py`, `frontend/src/App.js`).
        3.  **Key Components/Features:** Briefly describe the main parts of the backend and frontend.
        4.  **Data Models (if any):** Simple schema for database tables or API objects.

        Output the plan in a structured format (e.g., JSON or YAML). Structure example:
        ```json
        {{
          "stack": {{ "backend": "Python/FastAPI", "frontend": "React/Vite", "db": "None" }},
          "files": {{
            "backend/": {{
              "main.py": null,
              "models.py": null
            }},
            "frontend/": {{
               "src/": {{"App.jsx": null, "main.jsx": null}},
               "index.html": null,
               "package.json": null
            }},
            "README.md": null
          }},
          "components": ["API endpoint for X", "React component for Y"],
          "models": {{ "item": ["id", "name", "description"] }}
        }}
        ```
        """
        # IMPORTANT: This direct call bypasses the agent's main loop/memory.
        # Consider how to integrate this better if context from chat is needed.
        plan_response = await direct_llm_call(
            messages=[{"role": "user", "content": planning_prompt}],
            model_id=planning_model
            # Add specific params like thinking budget for Claude if needed
        )

        # TODO: Parse the plan_response (JSON/YAML) robustly
        try:
             # Attempt to parse JSON directly or extract from ```json ... ``` block
             import json
             # Basic extraction, needs improvement
             plan_json_str = plan_response.split('```json')[1].split('```')[0].strip()
             plan = json.loads(plan_json_str)
             _generated_apps[project_id]['plan'] = plan
        except Exception as parse_error:
             print(f"Failed to parse plan: {parse_error}\nRaw plan response:\n{plan_response}")
             raise ToolError("generate_app_tool", f"Failed to parse the generated project plan. Raw response: {plan_response[:500]}...")


        await _send_status_update(project_id, "STRUCTURE", "Creating project directories and files...")
        _create_project_structure(project_path, plan.get("files", {}))

        # 2. Code Generation Phase (File by File)
        await _send_status_update(project_id, "GENERATING", "Generating code for each file...")
        codegen_model = ModelType.GEMINI_25_PRO # Good for code, or Claude 3.7
        all_files_to_generate = []
        def list_files_recursive(base_path, structure):
            for name, content in structure.items():
                current_path = Path(name)
                if isinstance(content, dict):
                    list_files_recursive(base_path / current_path, content)
                else:
                    all_files_to_generate.append(str(base_path / current_path))

        list_files_recursive(Path("."), plan.get("files", {})) # Get relative paths

        for file_rel_path in all_files_to_generate:
            await _send_status_update(project_id, "GENERATING", f"Generating {file_rel_path}...")
            file_abs_path = project_path / file_rel_path

            # More context helps the LLM
            codegen_prompt = f"""
            Project Context:
            - User Prompt: "{prompt}"
            - Technology Stack: {plan.get('stack')}
            - Overall Plan: {plan.get('components')} {plan.get('models')}
            - Project File Structure: {list(all_files_to_generate)}

            Generate the complete, syntactically correct code content for the file: `{file_rel_path}`.
            Ensure the code aligns with the project context and technology stack.
            Only output the raw code for the file, without any explanations or markdown formatting.
            If the file is a configuration file (e.g. package.json, requirements.txt), generate appropriate content.
            """
            try:
                file_content = await direct_llm_call(
                    messages=[{"role": "user", "content": codegen_prompt}],
                    model_id=codegen_model
                )
                # Clean potentially generated explanations/markdown ```
                if file_content.strip().startswith("```"):
                    file_content = file_content.split('\n', 1)[1]
                    if file_content.strip().endswith("```"):
                         file_content = file_content.rsplit('\n', 1)[0]

                file_abs_path.write_text(file_content, encoding='utf-8')
                _generated_apps[project_id]['files'][file_rel_path] = "Generated"
            except Exception as gen_error:
                print(f"Error generating {file_rel_path}: {gen_error}")
                _generated_apps[project_id]['files'][file_rel_path] = f"Error: {gen_error}"
                # Decide whether to continue or fail the whole process
                await _send_status_update(project_id, "ERROR", f"Failed to generate code for {file_rel_path}.")
                _generated_apps[project_id]['error'] = f"Generation failed for {file_rel_path}"
                return # Stop generation

        # 3. Execution Phase (Install & Run)
        await _send_status_update(project_id, "EXECUTING", "Attempting to install dependencies and run the application...")

        # Example: Detect package.json for Node projects, requirements.txt for Python
        install_commands = []
        run_command = None
        if (project_path / "package.json").exists():
            install_commands.append("npm install") # Or pnpm install, yarn install
            # Try to find a start script in package.json or common frameworks
            run_command = "npm run dev" # Or npm start
        if (project_path / "requirements.txt").exists():
            install_commands.append("pip install -r requirements.txt")
            # Assume FastAPI/Uvicorn for Python backend example
            if (project_path / "backend" / "main.py").exists(): # Check structure from plan
                 run_command = "uvicorn backend.main:app --host 0.0.0.0 --port 8080" # Example port
            elif (project_path / "main.py").exists():
                 run_command = "uvicorn main:app --host 0.0.0.0 --port 8080"

        exec_log = []
        for cmd in install_commands:
             await _send_status_update(project_id, "EXECUTING", f"Running: {cmd}")
             log = await execute_code_tool(code=cmd, language="shell") # Execute within the project dir sandbox
             exec_log.append(f"$ {cmd}\n{log}")
             if "Exit Code: 0" not in log.split('\n')[0]: # Basic check for success
                 raise ToolError("generate_app_tool", f"Dependency installation failed: {cmd}. Logs:\n{log}")

        if run_command:
            await _send_status_update(project_id, "EXECUTING", f"Attempting to run: {run_command}")
            # Running the server needs to happen in the background *within the sandbox*
            # This is tricky. `execute_code_tool` is synchronous. Need a way to start
            # a background process *managed by the agent or a supervisor*.
            # Placeholder: Simulate success and provide a hypothetical local URL
            exec_log.append(f"$ {run_command} (Simulated background start)")
            _generated_apps[project_id]['logs'] = exec_log
            # IMPORTANT: This URL is hypothetical. Actual port mapping/access depends
            # on how the execution environment (Docker, local process) is set up.
            preview_port = 8080 # Example port used in run_command
            # If running in Docker, this needs to map to a host port
            _generated_apps[project_id]['preview_url'] = f"http://localhost:{preview_port}" # Adjust host/port as needed
            await _send_status_update(project_id, "READY", "Application generated and (simulated) running.", preview_url=_generated_apps[project_id]['preview_url'])
        else:
            _generated_apps[project_id]['logs'] = exec_log
            await _send_status_update(project_id, "READY", "Application code generated. No standard run command detected.")


    except Exception as e:
        print(f"Error during app generation flow for {project_id}: {e}")
        await _send_status_update(project_id, "ERROR", f"An error occurred: {e}")
        _generated_apps[project_id]['error'] = str(e)

# --- TODO: Add Tools for ---
# - Checking app generation status
# - Getting app logs
# - Providing feedback/requesting modifications (triggers regeneration)
# - Exporting app code (zipping the project folder)
