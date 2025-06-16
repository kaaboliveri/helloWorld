# maity/backend/app/tasks.py
import datetime
import asyncio
import json
from pathlib import Path
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from . import config
from .tools.web_automation import web_search_tool
from .llm_clients import direct_llm_call, ModelType, get_model_configuration
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# --- Scheduler Setup (as before) ---
jobstores = {
    'default': SQLAlchemyJobStore(url=config.TASK_DB_URL)
}
scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="UTC")

# --- Directory for Monitoring Results ---
MONITORING_RESULTS_DIR = Path(config.LOCAL_SANDBOX_DIR).resolve() / "monitoring_results"
MONITORING_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

def _get_task_results_filepath(task_id: str) -> Path:
    sanitized_task_id = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in task_id)
    return MONITORING_RESULTS_DIR / f"{sanitized_task_id}_results.json"

def _update_job_metadata(job_id: str, last_run_status: str, last_run_time: datetime.datetime, findings_count: int = 0):
    """
    Helper to update job metadata. Stores it in the task's JSON results file.
    # This helper updates metadata within the task's dedicated JSON results file.
    """
    logger.info(f"Updating job metadata for {job_id}: Last run: {last_run_time}, Status: {last_run_status}, Findings: {findings_count}")
    task_filepath = _get_task_results_filepath(job_id)
    try:
        results_data: Dict[str, Any] = {"findings": []}
        if task_filepath.exists():
            try:
                with open(task_filepath, 'r', encoding='utf-8') as f:
                    results_data = json.load(f)
                if not isinstance(results_data.get("findings"), list):
                    results_data["findings"] = []
            except json.JSONDecodeError:
                logger.warning(f"Results file for {job_id} was corrupted. Initializing with new metadata.", exc_info=True)
                results_data = {"findings": []}

        results_data['last_run_status'] = last_run_status
        results_data['last_run_time'] = last_run_time.isoformat()
        results_data['last_run_findings_count'] = findings_count

        current_job = scheduler.get_job(job_id)
        if current_job and current_job.kwargs:
            results_data.setdefault('topic', current_job.kwargs.get('topic', job_id))
            results_data.setdefault('keywords', current_job.kwargs.get('keywords', 'N/A'))
            results_data.setdefault('sources', current_job.kwargs.get('sources', 'N/A'))
            if hasattr(current_job.trigger, 'interval'):
                 results_data.setdefault('frequency_hours', current_job.trigger.interval.total_seconds() / 3600)

        with open(task_filepath, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, indent=2)
    except Exception as e:
        logger.error(f"Error updating job metadata file for {job_id}: {e}", exc_info=True)

def add_monitoring_task(topic: str, keywords: str, sources: str, frequency_hours: int) -> str:
    safe_topic = "".join(c if c.isalnum() or c in (' ', '_') else '_' for c in topic).replace(' ', '_')
    job_id = f"monitor_{safe_topic}_{int(datetime.datetime.now(datetime.timezone.utc).timestamp())}"

    logger.info(f"Scheduling job {job_id} for topic '{topic}' every {frequency_hours} hours.")
    scheduler.add_job(
        run_monitoring_check,
        trigger='interval',
        hours=frequency_hours,
        id=job_id,
        name=f"Monitoring: {topic}",
        replace_existing=True,
        kwargs={"job_id": job_id, "topic": topic, "keywords": keywords, "sources": sources},
        misfire_grace_time=3600
    )

    task_filepath = _get_task_results_filepath(job_id)
    initial_metadata = {
        "task_id": job_id,
        "topic": topic, "keywords": keywords, "sources": sources, "frequency_hours": frequency_hours,
        "scheduled_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "last_run_status": "Scheduled", "last_run_time": None, "last_run_findings_count": 0,
        "findings": []
    }
    try:
        with open(task_filepath, 'w', encoding='utf-8') as f:
            json.dump(initial_metadata, f, indent=2)
    except Exception as e:
        logger.error(f"Error creating initial metadata file for {job_id}: {e}", exc_info=True)
    return job_id

def list_monitoring_tasks() -> list:
    jobs = scheduler.get_jobs(jobstore='default')
    task_list = []
    for job in jobs:
        task_filepath = _get_task_results_filepath(job.id)
        metadata: Dict[str, Any] = {}
        if task_filepath.exists():
            try:
                with open(task_filepath, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
            except Exception as e:
                logger.warning(f"Could not read metadata for task {job.id}: {e}", exc_info=True)

        task_list.append({
            "id": job.id,
            "topic": metadata.get("topic", job.name.replace("Monitoring: ", "")),
            "keywords": metadata.get("keywords", job.kwargs.get('keywords') if job.kwargs else 'N/A'),
            "sources": metadata.get("sources", job.kwargs.get('sources') if job.kwargs else 'N/A'),
            "frequency_hours": metadata.get("frequency_hours", job.trigger.interval.total_seconds() / 3600 if hasattr(job.trigger, 'interval') else 'N/A'),
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else "N/A",
            "last_run_time": metadata.get('last_run_time'),
            "last_run_status": metadata.get('last_run_status', "Scheduled"),
            "last_run_findings_count": metadata.get('last_run_findings_count', 0)
        })
    return task_list

def get_monitoring_results(task_id: str) -> List[Dict[str, Any]]:
    task_filepath = _get_task_results_filepath(task_id)
    if task_filepath.exists():
        try:
            with open(task_filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            findings_list = data.get("findings", [])
            if isinstance(findings_list, list):
                try:
                    findings_list.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
                except Exception as sort_e:
                    logger.warning(f"Could not sort findings for task {task_id} due to: {sort_e}", exc_info=True)
            return findings_list
        except Exception as e:
            logger.error(f"Error reading results file for task {task_id}: {e}", exc_info=True)
            return [{"error": "Could not read results file.", "details": str(e)}]
    logger.info(f"No results file found for task {task_id}.")
    return []

async def run_monitoring_check(job_id: str, topic: str, keywords: str, sources: str):
    logger.info(f"Running monitoring check for job: {job_id}, Topic: '{topic}', Keywords: '{keywords}'")
    current_run_time = datetime.datetime.now(datetime.timezone.utc)
    new_findings_this_run_count = 0
    status_this_run = "Failed"

    try:
        search_query = f"{topic} {keywords}"
        logger.info(f"Performing web search for: '{search_query}' (Job: {job_id})")
        search_results_str = await web_search_tool(query=search_query)

        if not search_results_str or "No search results found." in search_results_str:
            logger.info(f"No web search results for job {job_id}.")
            status_this_run = "Completed - No Search Results"
            _update_job_metadata(job_id, status_this_run, current_run_time, 0)
            return

        llm_model_id = ModelType.O3_MINI.value
        summarization_prompt = f"""
        Analyze the following web search results for the topic "{topic}" with keywords "{keywords}".
        Identify and summarize up to 3-5 key distinct findings or updates.
        For each finding, provide a concise title and a brief summary (1-2 sentences).
        If multiple search results point to the same underlying event or information, synthesize them into a single finding.
        Focus on information that appears new or significant.
        Format each finding as:
        Title: <Descriptive Title>
        Summary: <Brief Summary>
        Source URLs: <comma-separated list of relevant URLs from search results if possible>
        ---
        If no new significant information is found, state "No significant new findings."

        Search Results:
        {search_results_str}
        ---
        Key Findings:
        """

        llm_messages = [{"role": "user", "content": summarization_prompt}]
        model_config = get_model_configuration(llm_model_id)

        summary_text = await direct_llm_call(
            messages=llm_messages, model_id=llm_model_id, **model_config.get("default_params", {})
        )

        if summary_text and summary_text.strip() and "No significant new findings." not in summary_text:
            logger.info(f"LLM summary for job {job_id} (first 200 chars): {summary_text[:200]}...")

            parsed_findings = []
            current_finding: Dict[str, Any] = {}
            for line in summary_text.strip().split('\n'):
                if line.startswith("Title:"):
                    if current_finding.get("title"):
                        parsed_findings.append(current_finding)
                        current_finding = {}
                    current_finding["title"] = line.replace("Title:", "").strip()
                elif line.startswith("Summary:"):
                    current_finding["summary"] = line.replace("Summary:", "").strip()
                elif line.startswith("Source URLs:"):
                    current_finding["source_urls"] = [url.strip() for url in line.replace("Source URLs:", "").split(',') if url.strip()]
                elif line.strip() == "---" and current_finding.get("title"):
                    parsed_findings.append(current_finding)
                    current_finding = {}
            if current_finding.get("title"):
                parsed_findings.append(current_finding)

            new_findings_for_storage = []
            for pf in parsed_findings:
                if pf.get("title") and pf.get("summary"):
                    new_findings_for_storage.append({
                        "timestamp": current_run_time.isoformat(),
                        "title": pf["title"],
                        "summary": pf["summary"],
                        "source_urls": pf.get("source_urls", []),
                        "source_type": sources,
                    })

            if new_findings_for_storage:
                new_findings_this_run_count = len(new_findings_for_storage)
                task_filepath = _get_task_results_filepath(job_id)
                all_task_data: Dict[str, Any] = {"findings": [], "topic": topic}
                if task_filepath.exists():
                    try:
                        with open(task_filepath, 'r', encoding='utf-8') as f:
                            all_task_data = json.load(f)
                        if not isinstance(all_task_data.get("findings"), list):
                            all_task_data["findings"] = []
                    except json.JSONDecodeError:
                        logger.warning(f"Results file for {job_id} was corrupted. Overwriting with new findings.", exc_info=True)
                        all_task_data["findings"] = []

                all_task_data["findings"] = new_findings_for_storage + all_task_data.get("findings", [])
                max_findings = getattr(config, 'MONITORING_MAX_FINDINGS_PER_TASK', 50)
                if len(all_task_data["findings"]) > max_findings:
                    all_task_data["findings"] = all_task_data["findings"][:max_findings]

                all_task_data.setdefault('topic', topic)
                all_task_data.setdefault('keywords', keywords)
                all_task_data.setdefault('sources', sources)

                with open(task_filepath, 'w', encoding='utf-8') as f:
                    json.dump(all_task_data, f, indent=2)
                status_this_run = f"Completed - {new_findings_this_run_count} New Findings"
            else:
                logger.info(f"LLM summary for {job_id} parsed, but no valid findings extracted.")
                status_this_run = "Completed - LLM Summary Parsed No Valid Findings"
        else:
            logger.info(f"LLM returned no summary or no significant findings for job {job_id}.")
            status_this_run = "Completed - No New Findings From LLM"

        _update_job_metadata(job_id, status_this_run, current_run_time, new_findings_this_run_count)
        logger.info(f"Monitoring check for {job_id} completed. Status: {status_this_run}.")

    except Exception as e:
        logger.error(f"Error during monitoring check for job {job_id}: {type(e).__name__} - {e}", exc_info=True)
        status_this_run = f"Failed: {type(e).__name__}"
        _update_job_metadata(job_id, status_this_run, current_run_time, 0)

def init_scheduler():
    if not scheduler.running:
        logger.info("Starting APScheduler...")
        scheduler.start()
    else:
        logger.info("APScheduler already running.")

def shutdown_scheduler():
    if scheduler.running:
        logger.info("Shutting down APScheduler...")
        scheduler.shutdown()
        logger.info("APScheduler shut down.")
