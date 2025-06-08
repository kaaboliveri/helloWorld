from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class ChatMessage(BaseModel):
    role: str # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    # Potentially add user config here like preferred model
    config: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    content: str
    conversation_id: str
    error: Optional[bool] = False
    debug_info: Optional[Dict[str, Any]] = None # For tool calls, model used etc.

class ToolCallInfo(BaseModel):
    tool_name: str
    tool_args: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None

class AppGenRequest(BaseModel):
    prompt: str
    conversation_id: Optional[str] = None # To associate with a chat

class AppGenStatusUpdate(BaseModel):
    conversation_id: str
    status: str # e.g., "PLANNING", "GENERATING", "EXECUTING", "READY", "ERROR"
    message: Optional[str] = None
    preview_url: Optional[str] = None
    logs: Optional[List[str]] = None

class AppGenResponse(BaseModel):
    conversation_id: str
    status: str
    message: str
    project_id: Optional[str] = None # ID to reference the generated app

# Add other models as needed (MonitoringRequest, CodeExecutionRequest, etc.)
