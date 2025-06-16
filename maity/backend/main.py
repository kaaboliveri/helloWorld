import os
import asyncio
import logging # Added
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field
from typing import Optional, List

# Existing imports
from backend.app import config # Added for config.LOG_LEVEL
from backend.app.agents import get_maity_agent, MaityAgent
from backend.app.tasks import scheduler, init_scheduler, shutdown_scheduler
from backend.app.models import ChatRequest, ChatResponse
from backend.app.tools.web_automation import close_browser

from backend.app.tools.monitoring import (
    setup_monitoring_tool as setup_monitoring_tool_action,
)
from backend.app.tasks import list_monitoring_tasks, get_monitoring_results
from openai_agents.tool import ToolError
from backend.app.tools.app_generator import active_appgen_websockets, generate_app_tool as generate_app_tool_action

# Logging Configuration
numeric_log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(
    level=numeric_log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Maity Backend starting up...")
    init_scheduler()
    yield
    logger.info("Maity Backend shutting down...")
    shutdown_scheduler()
    await close_browser()
    logger.info("Cleanup complete.")

app = FastAPI(
    title="Maity AI Agent Backend",
    description="Backend API for the Maity AI Agent, providing chat, tools, and task management.",
    version="0.1.0",
    lifespan=lifespan
)

origins = ["http://localhost", "http://localhost:3000", "http://127.0.0.1", "http://127.0.0.1:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    if not req.message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    agent_instance = await get_maity_agent(req.conversation_id)
    try:
        response_data = await agent_instance.handle_message(
            message=req.message,
            preferred_model=req.config.get("preferred_model") if req.config else None
        )
        return ChatResponse(**response_data)
    except Exception as e:
        logger.error(f"Unhandled exception in chat_endpoint: {type(e).__name__} - {e}", exc_info=True)
        return ChatResponse(
            content=f"An internal server error occurred: {str(e)}",
            conversation_id=agent_instance.conversation_id if agent_instance and hasattr(agent_instance, 'conversation_id') else req.conversation_id,
            error=True
        )

@app.websocket("/ws/chat/{conversation_id}")
async def websocket_chat_endpoint(websocket: WebSocket, conversation_id: str):
    await websocket.accept()
    logger.info(f"WebSocket connection established for conversation: {conversation_id}")
    agent = await get_maity_agent(conversation_id)
    try:
        while True:
            data = await websocket.receive_text()
            import json
            try:
                req_data = json.loads(data)
                message = req_data.get("message")
                config_data = req_data.get("config")
                if not message:
                    await websocket.send_text(json.dumps({"type": "error", "content": "Empty message received."}))
                    continue
                await websocket.send_text(json.dumps({"type": "status", "content": "Agent processing..."}))
                response_data = await agent.handle_message(
                    message=message,
                    preferred_model=config_data.get("preferred_model") if config_data else None
                )
                await websocket.send_text(json.dumps({
                    "type": "final_response",
                    "content": response_data["content"],
                    "conversation_id": response_data["conversation_id"],
                    "error": response_data["error"],
                    "debug_info": response_data.get("debug_info")
                }))
            except json.JSONDecodeError:
                 logger.warning("Invalid JSON received via WebSocket.", exc_info=True)
                 await websocket.send_text(json.dumps({"type": "error", "content": "Invalid JSON received."}))
            except Exception as e:
                 logger.error(f"Error in WebSocket handler for {conversation_id}: {type(e).__name__} - {e}", exc_info=True)
                 await websocket.send_text(json.dumps({"type": "error", "content": f"Server error: {str(e)}"}))
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for conversation: {conversation_id}")
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket connection for {conversation_id}: {type(e).__name__} - {e}", exc_info=True)

class MonitorSetupRequest(BaseModel):
    topic: str = Field(..., min_length=1, description="Descriptive name for the monitoring task")
    keywords: str = Field(..., min_length=1, description="Keywords or query for the search")
    sources: Optional[str] = "web_search"
    frequency_hours: int = Field(default=24, gt=0, description="Frequency in hours (must be > 0)")

class AppGenPromptRequest(BaseModel):
    prompt: str

@app.post("/api/monitor/setup", summary="Set up a new monitoring task", status_code=201)
async def setup_new_monitoring_task_endpoint(request_data: MonitorSetupRequest):
    try:
        logger.info(f"Received monitoring setup request: {request_data}")
        result_message = await setup_monitoring_tool_action(
            topic=request_data.topic,
            keywords=request_data.keywords,
            sources=request_data.sources,
            frequency_hours=request_data.frequency_hours
        )
        return {"message": result_message}
    except ToolError as e:
        logger.warning(f"ToolError in monitoring setup: {e.message}")
        raise HTTPException(status_code=400, detail=f"Tool Error: {e.message}")
    except Exception as e:
        logger.error(f"Error setting up monitoring task: {type(e).__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/monitor/tasks", summary="List all active monitoring tasks")
async def get_active_monitoring_tasks_endpoint():
    try:
        tasks = list_monitoring_tasks()
        return tasks
    except Exception as e:
        logger.error(f"Error listing monitoring tasks: {type(e).__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/monitor/results/{task_id}", summary="Get latest results for a monitoring task")
async def get_task_monitoring_results_endpoint(task_id: str):
    try:
        results = get_monitoring_results(task_id)
        return results
    except Exception as e:
        logger.error(f"Error getting monitoring results for task {task_id}: {type(e).__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/")
async def root():
    return {"message": "Welcome to the Maity AI Agent Backend!"}

@app.post("/api/app/generate", summary="Start a new app generation task")
async def start_app_generation(request_data: AppGenPromptRequest):
    if not request_data.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")
    try:
        logger.info(f"Starting app generation for prompt: '{request_data.prompt[:50]}...'")
        result_message = await generate_app_tool_action(prompt=request_data.prompt)
        project_id = None
        parts = result_message.split("Project ID: ")
        if len(parts) > 1:
            project_id_part = parts[1].split(".")[0]
            project_id = project_id_part.strip()

        if not project_id:
            logger.error(f"Could not reliably extract project_id from response: {result_message}")
            # Removed Query based regex for project_id extraction as it was problematic
            raise HTTPException(status_code=500, detail="Failed to start task or determine project ID from tool response.")

        return {"project_id": project_id, "initial_message": result_message}
    except ToolError as e:
        logger.warning(f"ToolError in app generation: {e.message}")
        raise HTTPException(status_code=400, detail=f"Tool Error: {e.message}")
    except Exception as e:
        logger.error(f"Error starting app generation: {type(e).__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.websocket("/ws/appgen/{project_id}")
async def websocket_appgen_status(websocket: WebSocket, project_id: str):
    await websocket.accept()
    logger.info(f"AppGen WebSocket connection established for project: {project_id}")
    active_appgen_websockets[project_id].append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(f"Received on /ws/appgen/{project_id}: {data} (ignoring)")
    except WebSocketDisconnect:
        logger.info(f"AppGen WebSocket disconnected for project: {project_id}")
    except Exception as e:
        logger.error(f"Error in AppGen WebSocket for {project_id}: {type(e).__name__} - {e}", exc_info=True)
    finally:
        if websocket in active_appgen_websockets.get(project_id, []):
            active_appgen_websockets[project_id].remove(websocket)
        if not active_appgen_websockets.get(project_id):
            if project_id in active_appgen_websockets:
                del active_appgen_websockets[project_id]
        logger.info(f"AppGen WebSocket for {project_id} cleaned up.")
