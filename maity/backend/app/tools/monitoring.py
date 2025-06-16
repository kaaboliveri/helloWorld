from openai_agents.tool import tool, ToolError
from ..tasks import add_monitoring_task, list_monitoring_tasks, get_monitoring_results
import logging # Added

logger = logging.getLogger(__name__) # Added

# --- Tool Definitions ---

@tool("Sets up automated monitoring for a specific topic.")
async def setup_monitoring_tool(topic: str, keywords: str, sources: str = "web_search", frequency_hours: int = 24) -> str:
    """
    Configures a new automated monitoring task (veille) for a given topic.
    The agent will periodically check for new information based on keywords
    from specified sources (e.g., 'web_search', specific websites - future).

    Args:
        topic: A descriptive name for the monitoring task (e.g., 'AI Agent Developments').
        keywords: Comma-separated keywords or a natural language query for the search.
        sources: Where to search (currently 'web_search', future: 'specific_urls', 'rss').
        frequency_hours: How often to check for updates, in hours (minimum 1).

    Returns:
        A confirmation message with the task ID.
    """
    logger.info(f"Setting up monitoring for topic: '{topic}', keywords: '{keywords[:50]}...', sources: '{sources}', freq: {frequency_hours}h")
    if frequency_hours < 1:
        logger.warning(f"Frequency hours {frequency_hours} is less than 1. Defaulting to 1 hour.")
        frequency_hours = 1
    try:
        task_id = add_monitoring_task(topic, keywords, sources, frequency_hours) # This function in tasks.py now also logs
        return f"Monitoring task '{topic}' configured with ID: {task_id}. Will check every {frequency_hours} hours."
    except Exception as e:
        logger.error(f"Error setting up monitoring for topic '{topic}': {e}", exc_info=True)
        raise ToolError(tool_name="setup_monitoring_tool", message=f"Failed to setup monitoring: {str(e)}")

@tool("Checks the status or retrieves the latest results for monitoring tasks.")
async def check_monitoring_tool(task_id: str = None) -> str:
    """
    Lists all active monitoring tasks or retrieves the latest results/findings
    for a specific monitoring task ID.

    Args:
        task_id: Optional. The ID of a specific task to get results for.
                 If omitted, lists all active tasks.

    Returns:
        A list of active tasks or the latest report for the specified task.
    """
    logger.info(f"Checking monitoring tasks (Task ID: {task_id if task_id else 'ALL'})")
    try:
        if task_id:
            results = get_monitoring_results(task_id) # This function in tasks.py now also logs
            if not results: # Assuming get_monitoring_results returns empty list if no results or task not found
                logger.info(f"No results found or task ID '{task_id}' does not exist.")
                return f"No results found for task ID '{task_id}', or task does not exist."

            report = f"Latest Findings for Task '{task_id}':\n"
            for finding in results[:10]:
                 report += f"- Timestamp: {finding.get('timestamp', 'N/A')}\n  Title: {finding.get('title', 'N/A')}\n  Summary: {finding.get('summary', 'N/A')}\n  Sources: {', '.join(finding.get('source_urls', []))}\n---\n"
            return report.strip()
        else:
            tasks = list_monitoring_tasks() # This function in tasks.py now also logs
            if not tasks:
                logger.info("No active monitoring tasks found.")
                return "No active monitoring tasks found."
            task_list_str = "Active Monitoring Tasks:\n" # Renamed to avoid conflict
            for task_item in tasks: # Renamed to avoid conflict
                task_list_str += (f"- ID: {task_item.get('id')}\n"
                                  f"  Topic: {task_item.get('topic')}\n"
                                  f"  Keywords: {task_item.get('keywords', 'N/A')}\n"
                                  f"  Frequency: {task_item.get('frequency_hours')}h\n"
                                  f"  Next Run: {task_item.get('next_run_time', 'N/A')}\n"
                                  f"  Last Run: {task_item.get('last_run_time', 'Never')}\n"
                                  f"  Status: {task_item.get('last_run_status', 'N/A')}\n"
                                  f"  Findings (last run): {task_item.get('last_run_findings_count', 0)}\n---\n")
            return task_list_str.strip()
    except Exception as e:
        logger.error(f"Error checking monitoring (Task ID: {task_id if task_id else 'ALL'}): {e}", exc_info=True)
        raise ToolError(tool_name="check_monitoring_tool", message=f"Failed to check monitoring status: {str(e)}")

# TODO: Add tools for pausing, resuming, or deleting monitoring tasks.
