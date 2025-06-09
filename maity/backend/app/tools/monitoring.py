from openai_agents.tool import tool, ToolError
from ..tasks import add_monitoring_task, list_monitoring_tasks, get_monitoring_results

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
    print(f"Setting up monitoring for topic: {topic}")
    if frequency_hours < 1:
        frequency_hours = 1 # Minimum frequency
    try:
        task_id = add_monitoring_task(topic, keywords, sources, frequency_hours)
        return f"Monitoring task '{topic}' configured with ID: {task_id}. Will check every {frequency_hours} hours."
    except Exception as e:
        print(f"Error setting up monitoring: {e}")
        raise ToolError(tool_name="setup_monitoring_tool", message=f"Failed to setup monitoring: {e}")

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
    print(f"Checking monitoring tasks (ID: {task_id})")
    try:
        if task_id:
            results = get_monitoring_results(task_id)
            if not results:
                return f"No results found for task ID '{task_id}', or task does not exist."
            # Format results nicely
            report = f"Latest Findings for Task '{task_id}':\n"
            # Assume results is a list of findings/articles with timestamps
            for finding in results[:10]: # Show latest 10
                 report += f"- {finding.get('timestamp')}: {finding.get('title', 'N/A')} ({finding.get('source_url', '')})\n"
            return report
        else:
            tasks = list_monitoring_tasks()
            if not tasks:
                return "No active monitoring tasks found."
            task_list = "Active Monitoring Tasks:\n"
            for task in tasks:
                task_list += f"- ID: {task.get('id')}, Topic: {task.get('topic')}, Freq: {task.get('frequency_hours')}h, Last Run: {task.get('last_run', 'Never')}\n"
            return task_list
    except Exception as e:
        print(f"Error checking monitoring: {e}")
        raise ToolError(tool_name="check_monitoring_tool", message=f"Failed to check monitoring status: {e}")

# TODO: Add tools for pausing, resuming, or deleting monitoring tasks.
