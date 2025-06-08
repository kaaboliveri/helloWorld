import os
from dotenv import load_dotenv

load_dotenv() # Load variables from .env file

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Model IDs
O3_MINI_MODEL_ID = os.getenv("O3_MINI_MODEL_ID", "o3-mini") # Provide default or ensure set
CLAUDE_37_SONNET_MODEL_ID = os.getenv("CLAUDE_37_SONNET_MODEL_ID", "claude-3.7-sonnet-20240715")
GEMINI_25_PRO_MODEL_ID = os.getenv("GEMINI_25_PRO_MODEL_ID", "gemini-2.5-pro-preview-03-25")

# Anthropic Specific
CLAUDE_THINKING_BUDGET_MS = int(os.getenv("CLAUDE_THINKING_BUDGET_MS", "5000")) # Default 5s

# Security
LOCAL_SANDBOX_DIR = os.getenv("LOCAL_SANDBOX_DIR", "./maity_sandbox")
REQUIRE_CONFIRMATION_LOCAL = os.getenv("REQUIRE_CONFIRMATION_LOCAL", "true").lower() == "true"

# Deployment
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))

# Tasks
TASK_DB_URL = os.getenv("TASK_DB_URL", "sqlite:///./maity_tasks.db")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Ensure critical keys are present
if not OPENAI_API_KEY:
    print("Warning: OPENAI_API_KEY not found in environment variables.")
if not ANTHROPIC_API_KEY:
    print("Warning: ANTHROPIC_API_KEY not found in environment variables.")
if not GOOGLE_API_KEY:
    print("Warning: GOOGLE_API_KEY not found in environment variables.")

# Create sandbox directory if it doesn't exist
os.makedirs(LOCAL_SANDBOX_DIR, exist_ok=True)
