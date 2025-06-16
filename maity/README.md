# Maity AI Agent

Maity is an open-source intelligent agent designed to transform user requests into concrete actions. It aims to bridge the gap between thought and execution, serving as a powerful productivity tool by leveraging multiple Large Language Models.

**Core Vision:** To provide an open, flexible, and powerful alternative to closed-source commercial agents, democratizing access to advanced AI agent capabilities. Maity aims to "convert your thoughts into actions" autonomously.

## Key Implemented Features

*   **Intelligent Conversational Agent:**
    *   Understands user requests via a chat interface.
    *   Allows selection between different LLMs (OpenAI o3 mini, Google Gemini 2.5 Pro, Anthropic Claude 3.7 Sonnet) for responses.
    *   Supports full Markdown rendering for AI responses, including tables, lists, bold/italic text, and links (opening in new tabs).
    *   Renders fenced code blocks with syntax highlighting and a "Copy to Clipboard" button.
    *   Manages conversation context (basic history).
*   **Web Interaction Tools:**
    *   `web_search_tool`: Performs web searches using DuckDuckGo.
    *   `browse_website_tool`: Navigates to a URL, extracts its text content, and uses an LLM to analyze or summarize that content based on a user's task description.
*   **Local Computer Interaction (Sandboxed):**
    *   Tools for listing files (`list_files_tool`), reading files (`read_file_tool`), and writing files (`write_file_tool`) within a configurable sandboxed directory (`./maity_sandbox` by default).
    *   `execute_code_tool`: Executes Python or shell script snippets provided as strings by writing them to temporary files within the sandbox and running them. Output (stdout, stderr, exit code) is captured. Includes basic timeout and output length limits.
*   **Automated Monitoring (Veille):**
    *   Users can set up recurring monitoring tasks for specific topics/keywords via the UI.
    *   The backend schedules these tasks using APScheduler.
    *   **Actual Monitoring Logic Implemented**: Scheduled tasks now execute `web_search_tool` and use an LLM (o3-mini by default) to summarize findings.
    *   Results (summarized findings with timestamps) are stored persistently in JSON files in the `maity_sandbox/monitoring_results` directory.
    *   UI allows viewing active tasks and their latest fetched results.
*   **Full-Stack App Generation (Experimental):**
    *   **Planning Phase**: User provides a prompt; an LLM (Claude 3.7 Sonnet by default) generates a project plan (tech stack, file structure, component/data model descriptions).
    *   **Structure Creation**: Creates the directory and empty file structure based on the plan.
    *   **Code Generation Phase**: Iterates through planned files; an LLM (Gemini 2.5 Pro by default) generates code for each file. Includes basic retry for file generation. Halts on critical file failures.
    *   **Basic Execution Phase**:
        *   Attempts to determine and run installation commands (e.g., `npm install`, `pip install`) using `execute_code_tool`. Halts on install failure.
        *   Attempts a short, simulated run of the application's start command to check for immediate errors.
    *   **Real-time Status Updates**: Frontend UI allows triggering app generation and displays detailed live status updates (planning, file generation progress, execution steps, errors, generated plan, hypothetical preview URL) via WebSockets.
    *   **Persistence**: App generation project state (plan, file status, logs) is saved to a JSON file (`maity_sandbox/appgen_projects.json`) to persist across Maity restarts.

## Current Status & Known Limitations

Maity is an advanced prototype with many functional components. While it demonstrates its core envisioned capabilities, please be aware of the following:

*   **App Generation is Highly Experimental:**
    *   The quality, correctness, and security of LLM-generated applications can vary significantly and are not guaranteed. Generated code will likely require manual review and refinement.
    *   The "execution" phase is a basic check for immediate startup errors, not a robust deployment or long-running process management solution. Generated apps are not automatically made accessible on the network by Maity.
    *   Error handling during generation is basic. The agent cannot yet intelligently recover from most code generation or execution errors.
*   **Security of `execute_code_tool`:**
    *   The tool executes code in a sandboxed directory but relies on script-based execution. While safer than direct `shell=True`, it is **not yet hardened for running untrusted code in a production environment.**
    *   Conceptual plans for containerized execution (using Docker) are in place but not yet implemented. **Use with extreme caution, especially if exposing Maity to untrusted users or prompts.**
*   **Monitoring Task Depth:** While monitoring tasks now execute, the analysis and summarization are based on a single LLM pass over search results. More sophisticated analysis or change detection over time is not yet implemented.
*   **Testing Coverage:** Initial unit and API tests have been added for some backend components, and basic frontend component tests are present. However, comprehensive test coverage (unit, integration, end-to-end) is still required for robust reliability.
*   **User Management & Data Persistence:** There are no user accounts. Chat history is in-memory per session (though `conversationId` can be persisted in `localStorage`). Monitoring task definitions are stored by APScheduler (e.g., in `maity_tasks.db`), and their results and app generation projects are stored as JSON files in the sandbox.
*   **Scalability:** The current setup (global dictionaries for WebSocket connections, in-memory agent instances) is designed for single-worker, local development or small-scale use.
*   **TODOs:** The codebase contains various "TODO" comments highlighting areas for future improvements and feature enhancements.

## Technologies

*   **Backend:** Python, FastAPI, OpenAI Agents SDK (for agent interaction patterns), Playwright (for web automation), APScheduler (for task scheduling).
*   **LLMs:** Designed for use with OpenAI (e.g., o3-mini), Google (e.g., Gemini 2.5 Pro), Anthropic (e.g., Claude 3.7 Sonnet). Requires API keys.
*   **Frontend:** React (with `react-scripts`), `axios`, `react-markdown`.
*   **Deployment:** Docker Compose (for local setup).

## Getting Started

**Prerequisites:**

*   Docker and Docker Compose installed.
*   Git installed.
*   API keys for OpenAI, Anthropic, and Google AI (or Vertex AI).

**Installation & Setup:**

1.  **Clone the repository:**
    ```bash
    git clone <repository_url> maity
    cd maity
    ```

2.  **Configure API Keys:**
    *   Copy the example environment file:
        ```bash
        cp .env.example .env
        ```
    *   Edit the `.env` file and add your actual API keys for `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `GOOGLE_API_KEY`.
    *   Review other settings in `.env` like `LOCAL_SANDBOX_DIR`, `LOG_LEVEL`. **Never commit your `.env` file with keys to version control.**

3.  **Build and Run with Docker Compose:**
    *   This command will build the backend and frontend images, then start the containers.
    ```bash
    docker-compose up --build -d
    ```
    *   The `-d` flag runs containers in detached mode. The first build might take time.

4.  **Access Maity:**
    *   **Frontend Application:** Should be available at `http://localhost:3000` (or the `FRONTEND_PORT` you set in `.env`). This is the primary interface.
    *   **Backend API Docs:** Auto-generated API docs (Swagger UI) available at `http://localhost:8000/docs` (or the `BACKEND_PORT`).

**Stopping the Application:**

```bash
docker-compose down
```

## Development Notes

(This section could be expanded with more details on contributing, code structure, etc. if desired)

*   **Logging:** Backend logging is configured in `main.py` and uses Python's `logging` module. Log level can be set via `LOG_LEVEL` in the `.env` file.
*   **Code Execution:** Be mindful of the security implications of the `execute_code_tool` as noted in "Known Limitations."

## Contributing

(Add contribution guidelines here when ready - e.g., code style, pull request process).

## License

(Specify the chosen open-source license here - e.g., MIT, Apache 2.0).
