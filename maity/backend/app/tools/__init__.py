# Make tools easily importable
from .web_automation import web_search_tool, browse_website_tool
from .local_system import (
    list_files_tool,
    read_file_tool,
    write_file_tool,
    execute_code_tool,
    run_shell_command_tool
)
from .app_generator import generate_app_tool
from .monitoring import setup_monitoring_tool, check_monitoring_tool

# List all available tools for registration in agents.py
ALL_TOOLS = [
    web_search_tool, browse_website_tool,
    list_files_tool, read_file_tool, write_file_tool,
    execute_code_tool, run_shell_command_tool,
    generate_app_tool,
    setup_monitoring_tool, check_monitoring_tool,
]
