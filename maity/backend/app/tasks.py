import datetime
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from . import config
from .agents import MaityAgent # Need access to the agent logic for running checks

# --- Scheduler Setup ---
jobstores = {
    'default': SQLAlchemyJobStore(url=config.TASK_DB_URL)
}
scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="UTC")

# --- Task Data Storage (Simple example using job metadata) ---
# A separate DB table might be better for storing results.

def add_monitoring_task(topic: str, keywords: str, sources: str, frequency_hours: int) -> str:
    """Adds a job to the scheduler for monitoring."""
    job_id = f"monitor_{topic.replace(' ', '_').lower()}_{datetime.datetime.now().timestamp()}"
    scheduler.add_job(
        run_monitoring_check,
        trigger='interval',
        hours=frequency_hours,
        id=job_id,
        name=f"Monitoring: {topic}",
        replace_existing=True,
        args=[job_id, topic, keywords, sources],
        misfire_grace_time=3600 # Allow 1 hour delay
    )
    print(f"Scheduled job {job_id} for topic '{topic}' every {frequency_hours} hours.")
    return job_id

def list_monitoring_tasks() -> list:
    """Lists scheduled monitoring jobs."""
    jobs = scheduler.get_jobs(jobstore='default')
    task_list = []
    for job in jobs:
        # Extract info stored during add_job or from job details
        task_list.append({
            "id": job.id,
            "topic": job.name.replace("Monitoring: ", ""),
            "frequency_hours": job.trigger.interval.total_seconds() / 3600 if hasattr(job.trigger, 'interval') else 'N/A',
            "next_run": job.next_run_time,
            "last_run": None # TODO: Store last run time/status
        })
    return task_list

def get_monitoring_results(task_id: str) -> list:
    """Retrieves results for a specific task (placeholder)."""
    # TODO: Implement result storage (e.g., in DB or files) associated with task_id
    print(f"Placeholder: Retrieving results for task {task_id}")
    # Example structure
    return [
        {"timestamp": datetime.datetime.now(datetime.timezone.utc), "title": "Placeholder Result 1", "source_url": "http://example.com/1"},
        {"timestamp": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1), "title": "Placeholder Result 2", "source_url": "http://example.com/2"},
    ]

# --- Task Execution Logic ---
async def run_monitoring_check(job_id: str, topic: str, keywords: str, sources: str):
    """The actual function executed by the scheduler."""
    print(f"Running monitoring check for job: {job_id}, Topic: {topic}")
    try:
        # Use the MaityAgent to perform the search/analysis
        # This requires careful handling of agent instances and context
        # Option 1: Create a temporary agent instance
        temp_agent = MaityAgent() # Needs careful state/config handling
        # Option 2: Have a shared agent instance or a dedicated monitoring agent pool

        # Construct a prompt for the agent
        prompt = f"Perform a monitoring check for the topic '{topic}'. Search for new information related to these keywords: '{keywords}'. Focus on sources: {sources}. Summarize any new findings since the last check (assume last check was {datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)})." # Need better time tracking

        # Execute the agent logic (this might involve multiple tool calls internally)
        # Using handle_message might not be ideal as it's chat-oriented.
        # Need a dedicated method or way to invoke agent for background tasks.
        # result = await temp_agent.run_background_task(prompt) # Conceptual method

        # Placeholder: Simulate finding results
        await asyncio.sleep(10) # Simulate work
        results = f"Found new article about '{keywords}' on example.com."
        print(f"Monitoring check for {job_id} completed. Result: {results}")

        # TODO: Store the results persistently (DB, file) linked to job_id
        # Store timestamp of this run

    except Exception as e:
        print(f"Error during monitoring check for job {job_id}: {e}")
        # Log the error appropriately

def init_scheduler():
    """Starts the scheduler if it's not already running."""
    if not scheduler.running:
        print("Starting APScheduler...")
        scheduler.start()
        print("APScheduler started.")
    else:
        print("APScheduler already running.")

def shutdown_scheduler():
    """Shuts down the scheduler gracefully."""
    if scheduler.running:
        print("Shutting down APScheduler...")
        scheduler.shutdown()
        print("APScheduler shut down.")
