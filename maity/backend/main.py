import os
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.app.agents import get_maity_agent, MaityAgent
from backend.app.tasks import scheduler, init_scheduler, shutdown_scheduler
from backend.app.models import ChatRequest, ChatResponse, AppGenStatusUpdate # Import necessary models
from backend.app.tools.web_automation import close_browser # Import browser cleanup

# --- App Lifecycle (for scheduler and browser cleanup) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Maity Backend starting up...")
    init_scheduler()
    # Any other async setup (e.g., DB connections)
    yield
    # Shutdown
    print("Maity Backend shutting down...")
    shutdown_scheduler()
    await close_browser() # Close shared playwright browser
    print("Cleanup complete.")

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Maity AI Agent Backend",
    description="Backend API for the Maity AI Agent, providing chat, tools, and task management.",
    version="0.1.0",
    lifespan=lifespan
)

# --- CORS Configuration ---
# Allow all origins for local development (restrict in production)
origins = [
    "http://localhost",
    "http://localhost:3000", # Default React/Vue ports
    "http://127.0.0.1",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Endpoints ---

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(
    req: ChatRequest,
    # agent: MaityAgent = Depends(get_maity_agent) # Depends on conversation_id from request path/body
):
    """
    Handles a single turn in a chat conversation.
    The agent will process the message, potentially use tools, and return a response.
    Use WebSocket endpoint for streaming responses.
    """
    if not req.message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Extract conversation_id for dependency injection (if not passed directly)
    # This assumes get_maity_agent correctly retrieves/creates based on req.conversation_id
    # If conversation_id is None, the agent will create a new one.
    agent_instance = await get_maity_agent(req.conversation_id)

    try:
        response_data = await agent_instance.handle_message(
            message=req.message,
            preferred_model=req.config.get("preferred_model") if req.config else None
        )
        # Ensure the response matches the Pydantic model
        return ChatResponse(**response_data)
    except Exception as e:
        # Log the exception properly
        print(f"Unhandled exception in chat_endpoint: {e}")
        # Return a generic error response matching the model
        return ChatResponse(
            content=f"An internal server error occurred: {e}",
            conversation_id=agent_instance.conversation_id, # Return the used/created ID
            error=True
        )


@app.websocket("/ws/chat/{conversation_id}")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    conversation_id: str,
    # How to get the agent instance here? Maybe fetch/create on first message?
):
    """
    Handles real-time chat communication over WebSocket.
    Streams agent responses and tool usage updates.
    """
    await websocket.accept()
    print(f"WebSocket connection established for conversation: {conversation_id}")
    agent = await get_maity_agent(conversation_id) # Get agent for this conversation

    try:
        while True:
            data = await websocket.receive_text()
            # Assume data is JSON string with user message: {"message": "...", "config": {...}}
            import json
            try:
                req_data = json.loads(data)
                message = req_data.get("message")
                config = req_data.get("config")
                if not message:
                    await websocket.send_text(json.dumps({"type": "error", "content": "Empty message received."}))
                    continue

                # Start agent processing - need to stream results back
                await websocket.send_text(json.dumps({"type": "status", "content": "Agent processing..."}))

                # --- Streaming Logic ---
                # The current handle_message isn't designed for streaming.
                # The OpenAI Agents SDK Runner needs modification or a different approach
                # to yield intermediate results (thoughts, tool calls, partial responses).
                # Placeholder: Run handle_message and send the final result.
                response_data = await agent.handle_message(
                    message=message,
                    preferred_model=config.get("preferred_model") if config else None
                )

                # Send final response
                await websocket.send_text(json.dumps({
                    "type": "final_response",
                    "content": response_data["content"],
                    "error": response_data["error"],
                    "debug_info": response_data.get("debug_info")
                }))

            except json.JSONDecodeError:
                 await websocket.send_text(json.dumps({"type": "error", "content": "Invalid JSON received."}))
            except Exception as e:
                 print(f"Error in WebSocket handler for {conversation_id}: {e}")
                 await websocket.send_text(json.dumps({"type": "error", "content": f"Server error: {e}"}))

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for conversation: {conversation_id}")
        # Clean up resources if necessary (e.g., remove agent instance if inactive?)
    except Exception as e:
        # Log unexpected errors during WebSocket lifecycle
        print(f"Unexpected error in WebSocket connection for {conversation_id}: {e}")
        await websocket.close(code=1011) # Internal Error code

# TODO: Add endpoints for:
# - /api/app/generate (POST, takes prompt, returns project_id, uses generate_app_tool) -> Use WebSocket for status
# - /ws/app/{project_id} (WebSocket for app generation status updates)
# - /api/app/{project_id}/export (GET, returns ZIP of the generated app)
# - /api/monitor (POST to create, GET to list/get results - uses monitoring tools)
# - Potentially endpoints for direct tool invocation if needed outside agent loop

# --- Root Endpoint ---
@app.get("/")
async def root():
    return {"message": "Welcome to the Maity AI Agent Backend!"}

# --- Optional: Serve Frontend ---
# If you want FastAPI to serve the static frontend build (simpler deployment)
# from fastapi.staticfiles import StaticFiles
# from fastapi.responses import FileResponse
#
# frontend_dir = "../frontend/build" # Adjust path to your frontend build output
#
# if os.path.exists(frontend_dir):
#     app.mount("/static", StaticFiles(directory=os.path.join(frontend_dir, "static")), name="static")
#
#     @app.get("/{full_path:path}")
#     async def serve_frontend(request: Request, full_path: str):
#         # Serves index.html for SPA routing, adjust if needed
#         file_path = os.path.join(frontend_dir, "index.html")
#         if os.path.exists(file_path):
#             return FileResponse(file_path)
#         else:
#             return {"message": "Frontend not built or found."}
# else:
#     print(f"Frontend directory '{frontend_dir}' not found. Frontend will not be served by FastAPI.")


# --- Development Server ---
# (Usually run via uvicorn command line, not here)
# if __name__ == "__main__":
#     import uvicorn
#     port = int(os.environ.get("PORT", 8000))
#     uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True) # Reload only for dev
