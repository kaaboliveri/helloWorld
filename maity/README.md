# Maity AI Agent

Maity is envisioned as a next-generation, open-source intelligent agent designed to transform user requests into concrete actions. It aims to bridge the gap between thought and execution, serving as a powerful productivity tool.

**Core Vision:** To provide an open, flexible, and powerful alternative to closed-source commercial agents, democratizing access to advanced AI agent capabilities. Maity aims to "convert your thoughts into actions" autonomously.

## Key Features (Based on PRD)

*   **Intelligent Conversational Agent:** Understands requests, selects appropriate LLMs (OpenAI o3 mini, Gemini 2.5 Pro, Claude 3.7 Sonnet), and manages conversation context.
*   **Deep Research:** Automates in-depth investigation of topics using web browsing and LLM synthesis.
*   **Web Automation:** Controls a web browser (via Playwright) to perform tasks like filling forms, navigation, and data extraction.
*   **Local Computer Interaction (Sandboxed):** Interacts with the local filesystem and executes code within a secure sandbox environment (`./maity_sandbox` by default). **Requires careful security considerations.**
*   **Automated Monitoring (Veille):** Allows users to set up recurring checks for new information on specific topics.
*   **Advanced Code & Content Generation:** Assists with coding (generation, debugging, explanation) and writing structured documents.
*   **Full-Stack App Generation (Bolt.diy Inspired):** Generates complete web application source code from natural language prompts, attempts execution, and allows iterative refinement.

## Technologies

*   **Backend:** Python, FastAPI, OpenAI Agents SDK, Playwright, APScheduler
*   **LLMs:** OpenAI o3 mini, Google Gemini 2.5 Pro, Anthropic Claude 3.7 Sonnet (Requires API keys)
*   **Frontend:** (To be implemented - e.g., React, Vue.js)
*   **Deployment:** Docker Compose (for local setup)

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
    *   Review other settings in `.env` like `LOCAL_SANDBOX_DIR` if needed. **Never commit your `.env` file with keys to version control.**

3.  **Build and Run with Docker Compose:**
    *   This command will build the backend (including installing Python dependencies and Playwright browsers) and frontend images, then start the containers.
    ```bash
    docker-compose up --build -d
    ```
    *   The `-d` flag runs the containers in detached mode (in the background).
    *   The first build might take some time, especially the Playwright browser downloads.

4.  **Access Maity:**
    *   **Backend API:** Should be available at `http://localhost:8000` (or the `BACKEND_PORT` you set). You can access the auto-generated API docs at `http://localhost:8000/docs`.
    *   **Frontend:** Should be available at `http://localhost:3000` (or the `FRONTEND_PORT` you set). **Note:** The frontend code provided is a basic placeholder and needs full implementation.

**Stopping the Application:**

```bash
docker-compose down
```
Development Notes

The provided code is a skeleton based on the PRD. Significant implementation is required within the tool functions (backend/app/tools/), agent logic (backend/app/agents.py), error handling, state management, WebSocket streaming, and the entire frontend.

Security: The local_system.py tool is particularly sensitive. The current implementation includes basic path validation but requires much more robust sandboxing and security hardening before being used in any real environment. User confirmation mechanisms also need proper implementation.

Frontend: The frontend needs to be built using a framework like React or Vue, implementing the UI components described in the PRD (Chat, Code Editor, App Preview, Monitoring Dashboard) and connecting to the backend API and WebSocket.

LLM Model IDs: Ensure the model IDs in .env and config.py match the exact, currently available IDs from OpenAI, Anthropic, and Google.

Contributing

(Add contribution guidelines here when ready - e.g., code style, pull request process).

License

(Specify the chosen open-source license here - e.g., MIT, Apache 2.0).
