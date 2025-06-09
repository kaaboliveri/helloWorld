import asyncio
import time
from typing import List, Dict, Optional, Any
from openai_agents import Agent, Runner, ToolError, HandoffRefusalError, tool
from .llm_clients import ModelType, get_model_configuration # Use our config helper
from .tools import ALL_TOOLS # Import the list of all tool functions
from . import config # For base instructions etc.

# --- Agent State Management (In-Memory Example) ---
# Store conversation history per conversation_id
_conversations: Dict[str, List[Dict[str, Any]]] = {}

class MaityAgent:
    """
    The main Maity Agent class orchestrating LLM calls and tool usage
    using the OpenAI Agents SDK.
    """
    def __init__(self, conversation_id: Optional[str] = None):
        # Basic system prompt - Should be refined significantly
        self.base_instructions = f"""
        You are Maity, a highly capable AI agent designed to turn user thoughts into actions.
        Your primary goal is to understand user requests, plan the necessary steps,
        and utilize available tools to accomplish tasks autonomously and efficiently.

        Available Models:
        - {ModelType.O3_MINI.value}: Fast, cost-effective for simple tasks or conversation.
        - {ModelType.GEMINI_25_PRO.value}: Strong coding, multimodal capabilities, good reasoning.
        - {ModelType.CLAUDE_37_SONNET.value}: Excellent reasoning, long context handling, strong writing, computer use potential, uses 'thinking' budget.

        Core Capabilities (Tools):
        - Web Interaction: Searching the web, browsing specific pages to extract info.
        - Local System (Sandboxed): Listing files, reading/writing files, executing code (Python, Shell) within the secure sandbox ('{config.LOCAL_SANDBOX_DIR}'). Requires confirmation for write/execute if enabled.
        - Application Generation: Creating full-stack web apps from prompts.
        - Monitoring: Setting up and checking automated topic monitoring.

        Interaction Flow:
        1. Understand the user's request fully. Ask clarifying questions if needed.
        2. Choose the most appropriate LLM for the task (or use default if unsure). Consider complexity, cost, required capabilities (coding, long context).
        3. Plan the steps required.
        4. Execute the plan, using the available tools. Announce which tool you are about to use and why.
        5. If a tool fails, analyze the error and try to recover or ask the user for guidance.
        6. Provide clear, concise, and well-formatted results to the user. Cite sources for research. Format code blocks appropriately.
        7. For local system actions or app generation, be mindful of the sandbox limitations and security confirmations.
        """
        self.conversation_id = conversation_id if conversation_id else str(time.time())
        if self.conversation_id not in _conversations:
            _conversations[self.conversation_id] = [{"role": "system", "content": self.base_instructions}]

    def _get_history(self) -> List[Dict[str, Any]]:
        """Retrieves the current conversation history."""
        return _conversations.get(self.conversation_id, [])

    def _add_message(self, role: str, content: Any):
        """Adds a message to the conversation history."""
        # TODO: Implement context window management (summarization, trimming)
        history = self._get_history()
        history.append({"role": role, "content": content})
        _conversations[self.conversation_id] = history # Update


    async def handle_message(self, message: str, preferred_model: Optional[str] = None) -> Dict[str, Any]:
        """
        Handles an incoming user message, runs the agent loop, and returns the response.
        """
        print(f"Handling message for conversation {self.conversation_id}: {message[:100]}...")
        self._add_message("user", message)

        # --- Model Selection Logic ---
        # TODO: Implement smarter model selection based on message content/history
        selected_model_id = preferred_model or ModelType.CLAUDE_37_SONNET.value # Default to Claude 3.7
        model_config = get_model_configuration(selected_model_id)
        print(f"Selected model: {selected_model_id}")

        # --- Agent and Runner Setup (using OpenAI Agents SDK) ---
        # Create agent instance for this run
        sdk_agent = Agent(
            name="MaityCoreAgent",
            instructions=None, # Instructions are part of the history now
            model=selected_model_id, # SDK needs the model ID string
            tools=ALL_TOOLS,
            # Pass model-specific settings if the SDK supports it
            # Example for Anthropic thinking budget (syntax might vary):
            model_settings={
                "provider_settings": {
                    "anthropic": model_config.get("default_params", {})
                }
            } if selected_model_id == ModelType.CLAUDE_37_SONNET else None
        )

        # Create a runner for this interaction
        runner = Runner(agent=sdk_agent) # Runner manages the loop

        response_content = "An unexpected error occurred."
        final_output = None
        tool_calls_info = []
        error_occurred = False
        debug_info = {"model_used": selected_model_id, "tool_calls": tool_calls_info}

        try:
            # Run the agent loop
            # The runner takes the full message history
            run_result = await runner.run(messages=self._get_history())

            # Process the result
            final_output = run_result.final_output # The assistant's final message content
            response_content = final_output

            # Add assistant response to history
            self._add_message("assistant", response_content)

            # Extract tool call information (if the SDK provides it easily)
            # This part depends heavily on the SDK's RunResult structure
            # Example:
            # for step in run_result.steps:
            #     if step.type == 'tool_call':
            #         tool_calls_info.append({
            #             "tool_name": step.tool_name,
            #             "tool_args": step.tool_input,
            #             "result": step.result, # Might be truncated
            #             "error": step.error
            #         })

        except ToolError as e:
            error_msg = f"Error using tool '{e.tool_name}': {e.message}"
            print(error_msg)
            response_content = f"(Agent error: {error_msg})"
            self._add_message("assistant", response_content) # Log error as assistant message
            error_occurred = True
            debug_info["error"] = error_msg
        except HandoffRefusalError as e:
            error_msg = f"Agent refused to hand off: {e}"
            print(error_msg)
            response_content = f"(Agent error: {error_msg})"
            self._add_message("assistant", response_content)
            error_occurred = True
            debug_info["error"] = error_msg
        except Exception as e:
            # Catch potential API errors, SDK internal errors, etc.
            error_msg = f"An unexpected error occurred during agent execution: {e}"
            print(error_msg)
            response_content = f"(System error: Please try again later. Details: {e})"
            # Don't add this raw error to history usually, but log it
            error_occurred = True
            debug_info["error"] = error_msg
            # Potentially add a generic error message to history
            self._add_message("assistant", "I encountered an unexpected issue. Please try rephrasing your request or try again later.")


        return {
            "content": response_content,
            "conversation_id": self.conversation_id,
            "error": error_occurred,
            "debug_info": debug_info
        }


# --- FastAPI Dependency Injection ---
# Manage agent instances per conversation
_agent_instances: Dict[str, MaityAgent] = {}

async def get_maity_agent(conversation_id: str) -> MaityAgent:
    """ FastAPI dependency to get or create an agent instance for a conversation. """
    if conversation_id not in _agent_instances:
        print(f"Creating new MaityAgent for conversation: {conversation_id}")
        _agent_instances[conversation_id] = MaityAgent(conversation_id=conversation_id)
    # TODO: Add logic for cleaning up old agent instances/conversations
    return _agent_instances[conversation_id]
