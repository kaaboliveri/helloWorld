import os
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field # Import BaseModel and Field for request body
from typing import Optional, List # For type hinting

# Existing imports
from backend.app.agents import get_maity_agent, MaityAgent
from backend.app.tasks import scheduler, init_scheduler, shutdown_scheduler # list_monitoring_tasks, get_monitoring_results are here
from backend.app.models import ChatRequest, ChatResponse # AppGenStatusUpdate removed as it's not used here
from backend.app.tools.web_automation import close_browser

# Import monitoring tools (functions that call task management)
from backend.app.tools.monitoring import (
    setup_monitoring_tool as setup_monitoring_tool_action, # Alias to avoid confusion with endpoint
    # list_monitoring_tasks, # This is directly from tasks.py
    # get_monitoring_results # This is directly from tasks.py
)
# Import task management functions directly for listing/getting results
from backend.app.tasks import list_monitoring_tasks, get_monitoring_results

from openai_agents.tool import ToolError # To catch errors from tools

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Maity Backend starting up...")
    init_scheduler()
    yield
    print("Maity Backend shutting down...")
    shutdown_scheduler()
    await close_browser()
    print("Cleanup complete.")

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

# --- Existing Chat Endpoints ---
@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest): # Removed Depends(get_maity_agent) to match original instruction
    if not req.message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    agent_instance = await get_maity_agent(req.conversation_id) # conversation_id can be None
    try:
        response_data = await agent_instance.handle_message(
            message=req.message,
            preferred_model=req.config.get("preferred_model") if req.config else None
        )
        return ChatResponse(**response_data)
    except Exception as e:
        print(f"Unhandled exception in chat_endpoint: {type(e).__name__} - {e}")
        return ChatResponse(
            content=f"An internal server error occurred: {str(e)}",
            conversation_id=agent_instance.conversation_id if agent_instance else req.conversation_id, # Ensure conv_id is returned
            error=True
        )

@app.websocket("/ws/chat/{conversation_id}")
async def websocket_chat_endpoint(websocket: WebSocket, conversation_id: str):
    await websocket.accept()
    print(f"WebSocket connection established for conversation: {conversation_id}")
    agent = await get_maity_agent(conversation_id)
    try:
        while True:
            data = await websocket.receive_text()
            import json # Keep import local to this scope
            try:
                req_data = json.loads(data)
                message = req_data.get("message")
                config = req_data.get("config")
                if not message:
                    await websocket.send_text(json.dumps({"type": "error", "content": "Empty message received."}))
                    continue
                await websocket.send_text(json.dumps({"type": "status", "content": "Agent processing..."}))
                response_data = await agent.handle_message(
                    message=message,
                    preferred_model=config.get("preferred_model") if config else None
                )
                await websocket.send_text(json.dumps({
                    "type": "final_response", # Ensure this matches frontend expectation
                    "content": response_data["content"],
                    "conversation_id": response_data["conversation_id"], # Send back conversation_id
                    "error": response_data["error"],
                    "debug_info": response_data.get("debug_info")
                }))
            except json.JSONDecodeError:
                 await websocket.send_text(json.dumps({"type": "error", "content": "Invalid JSON received."}))
            except Exception as e:
                 print(f"Error in WebSocket handler for {conversation_id}: {type(e).__name__} - {e}")
                 await websocket.send_text(json.dumps({"type": "error", "content": f"Server error: {str(e)}"}))
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for conversation: {conversation_id}")
    except Exception as e:
        print(f"Unexpected error in WebSocket connection for {conversation_id}: {type(e).__name__} - {e}")
        # await websocket.close(code=1011) # Avoid closing if already closed or in error state

# --- Pydantic Models for Monitoring API ---
class MonitorSetupRequest(BaseModel):
    topic: str = Field(..., min_length=1, description="Descriptive name for the monitoring task")
    keywords: str = Field(..., min_length=1, description="Keywords or query for the search")
    sources: Optional[str] = "web_search"
    frequency_hours: int = Field(default=24, gt=0, description="Frequency in hours (must be > 0)")


# --- Monitoring API Endpoints ---

@app.post("/api/monitor/setup", summary="Set up a new monitoring task", status_code=201) # Added status_code
async def setup_new_monitoring_task_endpoint(request_data: MonitorSetupRequest): # Renamed for clarity
    """
    Configures a new automated monitoring task.
    """
    try:
        print(f"Received monitoring setup request: {request_data}")
        # setup_monitoring_tool_action is the imported tool function which calls tasks.add_monitoring_task
        result_message = await setup_monitoring_tool_action(
            topic=request_data.topic,
            keywords=request_data.keywords,
            sources=request_data.sources,
            frequency_hours=request_data.frequency_hours
        )
        return {"message": result_message}
    except ToolError as e: # Catch errors specifically raised by the tool
        raise HTTPException(status_code=400, detail=f"Tool Error: {e.message}")
    except Exception as e:
        print(f"Error setting up monitoring task: {type(e).__name__} - {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/monitor/tasks", summary="List all active monitoring tasks")
async def get_active_monitoring_tasks_endpoint(): # Renamed for clarity
    """
    Lists all currently scheduled monitoring tasks.
    """
    try:
        # list_monitoring_tasks is directly from tasks.py (sync)
        tasks = list_monitoring_tasks()
        return tasks
    except Exception as e:
        print(f"Error listing monitoring tasks: {type(e).__name__} - {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/monitor/results/{task_id}", summary="Get latest results for a monitoring task")
async def get_task_monitoring_results_endpoint(task_id: str): # Renamed for clarity
    """
    Retrieves the latest findings for a specific monitoring task ID.
    """
    try:
        # get_monitoring_results is directly from tasks.py (sync)
        results = get_monitoring_results(task_id)
        # The placeholder in tasks.py returns a list.
        # If it were to return None for a non-existent task_id:
        # if results is None:
        #     raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found or no results yet.")
        # For now, it will always return a list (possibly empty if no actual results are stored)
        return results
    except Exception as e:
        print(f"Error getting monitoring results for task {task_id}: {type(e).__name__} - {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# --- Root Endpoint ---
@app.get("/")
async def root():
    return {"message": "Welcome to the Maity AI Agent Backend!"}

# (Comment out or remove unused appgen endpoints if not being developed due to blockages)
# @app.post("/api/app/generate") ...
# @app.websocket("/ws/appgen/{project_id}") ...
