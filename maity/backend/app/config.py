import os
import logging # Added
from dotenv import load_dotenv

load_dotenv() # Load variables from .env file
logger = logging.getLogger(__name__) # Added

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Model IDs
O3_MINI_MODEL_ID = os.getenv("O3_MINI_MODEL_ID", "o3-mini")
CLAUDE_37_SONNET_MODEL_ID = os.getenv("CLAUDE_37_SONNET_MODEL_ID", "claude-3.7-sonnet-20240715")
GEMINI_25_PRO_MODEL_ID = os.getenv("GEMINI_25_PRO_MODEL_ID", "gemini-2.5-pro-preview-03-25")

# Anthropic Specific
CLAUDE_THINKING_BUDGET_MS = int(os.getenv("CLAUDE_THINKING_BUDGET_MS", "5000"))

# Security
LOCAL_SANDBOX_DIR = os.getenv("LOCAL_SANDBOX_DIR", "./maity_sandbox")
REQUIRE_CONFIRMATION_LOCAL = os.getenv("REQUIRE_CONFIRMATION_LOCAL", "true").lower() == "true"
EXECUTE_CODE_MAX_OUTPUT_LENGTH = int(os.getenv("EXECUTE_CODE_MAX_OUTPUT_LENGTH", "20000"))

# Deployment
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))

# Tasks / Monitoring
TASK_DB_URL = os.getenv("TASK_DB_URL", "sqlite:///./maity_tasks.db")
MONITORING_MAX_FINDINGS_PER_TASK = int(os.getenv("MONITORING_MAX_FINDINGS_PER_TASK", "50"))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


# --- Feature Flags ---
USE_CONTAINER_EXECUTION = os.getenv("USE_CONTAINER_EXECUTION", "False").lower() == "true"


# --- App Generation Specific Configuration ---
APP_GEN_CRITICAL_FILE_PATTERNS = [
    "package.json",       # Node.js project manifest
    "requirements.txt",   # Python project dependencies
    "pom.xml",            # Java Maven project
    "build.gradle",       # Java/Android Gradle project
    "main.py",            # Common Python entry point
    "app.py",             # Common Python Flask/FastAPI entry point
    "server.js",          # Common Node.js entry point
    "index.js",           # Common Node.js/Frontend entry point
    "Program.cs",         # C# entry point
    "Main.java",          # Java entry point
    "Dockerfile",         # Containerization definition
    "docker-compose.yml"  # Multi-container definition
]
# Example: Add another config if needed
# APP_GEN_MAX_RETRIES_FILE_GEN = int(os.getenv("APP_GEN_MAX_RETRIES_FILE_GEN", "1"))


# Ensure critical keys are present
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY not found in environment variables.")
if not ANTHROPIC_API_KEY:
    logger.warning("ANTHROPIC_API_KEY not found in environment variables.")
if not GOOGLE_API_KEY:
    logger.warning("GOOGLE_API_KEY not found in environment variables.")

# Create sandbox directory if it doesn't exist
# This should be done early, as other parts of config might rely on this path (e.g. TASK_DB_URL default)
try:
    os.makedirs(LOCAL_SANDBOX_DIR, exist_ok=True)
    logger.info(f"Sandbox directory '{LOCAL_SANDBOX_DIR}' ensured (exists or was created).")
except OSError as e:
    logger.error(f"Could not create sandbox directory '{LOCAL_SANDBOX_DIR}': {e}", exc_info=True)
    # Depending on severity, might want to raise an exception here to halt startup if sandbox is critical
