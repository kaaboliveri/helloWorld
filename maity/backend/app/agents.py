import asyncio
import time
import logging # Added
from typing import List, Dict, Optional, Any
from openai_agents import Agent, Runner, ToolError, HandoffRefusalError, tool
from .llm_clients import ModelType, get_model_configuration
from .tools import ALL_TOOLS
from . import config

logger = logging.getLogger(__name__) # Added

_conversations: Dict[str, List[Dict[str, Any]]] = {}

class MaityAgent:
    def __init__(self, conversation_id: Optional[str] = None):
        self.base_instructions = f"""
        You are Maity, a highly capable AI agent...
        Core Capabilities (Tools):
        - Local System (Sandboxed): ... ('{config.LOCAL_SANDBOX_DIR}')...
        ... (rest of instructions as before)
        """ # Base instructions kept for brevity, should be full version

        new_conv_id_generated = False
        if conversation_id is None:
            conversation_id = f"conv_{time.time()}_{uuid.uuid4().hex[:8]}" # More unique ID
            new_conv_id_generated = True

        self.conversation_id = conversation_id
        if self.conversation_id not in _conversations:
            _conversations[self.conversation_id] = [{"role": "system", "content": self.base_instructions}]
            logger.info(f"Initialized new conversation history for ID: {self.conversation_id} (Generated: {new_conv_id_generated})")
        else:
            logger.info(f"Using existing conversation history for ID: {self.conversation_id}")


    def _get_history(self) -> List[Dict[str, Any]]:
        return _conversations.get(self.conversation_id, [])

    def _add_message(self, role: str, content: Any):
        # TODO (Advanced Feature): Implement more sophisticated context window management (e.g., summarization, token-based trimming, vector DB for long-term memory).
        history = self._get_history()
        history.append({"role": role, "content": content})
        # Limit history size (example: last 50 messages)
        max_history = getattr(config, 'MAX_CONVERSATION_HISTORY', 50)
        if len(history) > max_history:
            # Keep system prompt + last N-1 messages
            history = [history[0]] + history[-(max_history-1):]
        _conversations[self.conversation_id] = history
        logger.debug(f"Added message to history for {self.conversation_id}. Role: {role}, New history length: {len(history)}")


    async def handle_message(self, message: str, preferred_model: Optional[str] = None) -> Dict[str, Any]:
        logger.info(f"Handling message for conversation {self.conversation_id}: {message[:100]}...")
        self._add_message("user", message)

        # --- Conceptual Enhancements for Model Selection (comments as added previously) ---

        selected_model_id = preferred_model or ModelType.CLAUDE_37_SONNET.value
        model_config = get_model_configuration(selected_model_id)
        logger.info(f"Selected model for main interaction: {selected_model_id} (Conversation: {self.conversation_id})")

        sdk_agent = Agent(
            name="MaityCoreAgent",
            instructions=None,
            model=selected_model_id,
            tools=ALL_TOOLS,
            model_settings={
                "provider_settings": {"anthropic": model_config.get("default_params", {})}
            } if selected_model_id == ModelType.CLAUDE_37_SONNET else None
        )
        runner = Runner(agent=sdk_agent)
        response_content = "An unexpected error occurred."
        debug_info: Dict[str, Any] = {"model_used": selected_model_id, "tool_calls": []}

        try:
            # --- Conceptual Enhancements for Agent's Internal Planning & Tool Use (comments as added previously) ---

            run_result = await runner.run(messages=self._get_history())
            response_content = run_result.final_output
            self._add_message("assistant", response_content)
            logger.info(f"Agent response for {self.conversation_id} (first 100 chars): {response_content[:100] if response_content else 'None'}")

            # --- Conceptual Enhancements for Tool Call Info Extraction (comments as before) ---
            # if hasattr(run_result, 'steps'):
            #     for step in run_result.steps: ... debug_info["tool_calls"].append(...)

        except ToolError as e:
            error_msg = f"Error using tool '{e.tool_name}': {e.message}"
            logger.warning(f"ToolError in conversation {self.conversation_id} (Tool: {e.tool_name}): {e.message}", exc_info=False) # exc_info=False as ToolError is specific
            response_content = f"(Agent error: {error_msg})"
            self._add_message("assistant", response_content)
            debug_info["error"] = error_msg
            # --- Conceptual Enhancements for Tool Error Handling & Recovery (comments as added previously) ---

        except HandoffRefusalError as e:
            error_msg = f"Agent refused to hand off: {e}"
            logger.warning(f"HandoffRefusalError in conversation {self.conversation_id}: {error_msg}", exc_info=True)
            response_content = f"(Agent error: {error_msg})"
            self._add_message("assistant", response_content)
            debug_info["error"] = error_msg

        except Exception as e:
            error_msg = f"An unexpected error occurred in agent: {type(e).__name__} - {str(e)}"
            logger.error(f"Unexpected error in handle_message for conversation {self.conversation_id}: {error_msg}", exc_info=True)
            response_content = f"(System error: I encountered an issue. Please try again or rephrase.)"
            debug_info["error"] = error_msg
            if not any(m['role'] == 'assistant' and m['content'] == response_content for m in self._get_history()[-2:]):
                 self._add_message("assistant", "I encountered an unexpected issue. Please try rephrasing your request or try again later.")

        return {
            "content": response_content,
            "conversation_id": self.conversation_id,
            "error": bool(debug_info.get("error")),
            "debug_info": debug_info
        }

_agent_instances: Dict[str, MaityAgent] = {}
# Simple in-memory cache cleanup strategy (conceptual)
MAX_AGENT_INSTANCES = 100 # Example limit
AGENT_INSTANCE_EXPIRY_SECONDS = 3600 # Example: 1 hour

async def get_maity_agent(conversation_id: Optional[str]) -> MaityAgent:
    """ FastAPI dependency to get or create an agent instance for a conversation. """

    # Basic LRU-like cleanup for old instances if cache is too large
    # This is very basic; a proper LRU cache with TTL would be better for production
    if len(_agent_instances) > MAX_AGENT_INSTANCES:
        # Find the oldest (by some metric, e.g. last access if tracked, or just random for simplicity here)
        # For simplicity, removing the first one found if over limit. Not true LRU.
        try:
            oldest_id = next(iter(_agent_instances)) # Get first key
            logger.info(f"Max agent instances ({MAX_AGENT_INSTANCES}) reached. Removing oldest instance: {oldest_id}")
            del _agent_instances[oldest_id]
        except StopIteration: # Should not happen if len > 0
            pass
        except Exception as e:
            logger.warning(f"Error during basic agent instance cleanup: {e}")


    # If conversation_id is None, MaityAgent constructor will create a new unique ID
    # We need to ensure that if a None ID is passed, we create *one* agent for that request
    # and then use its generated ID if we need to store/retrieve it for that specific None-ID session.
    # However, the current design uses the *actual* conversation_id (even if generated) as the key.

    true_conv_id = conversation_id # If None, MaityAgent will generate one.

    if true_conv_id is None: # A new agent is requested without a specific ID
        logger.info(f"Request for agent with no ID. Creating a new MaityAgent instance.")
        agent = MaityAgent(conversation_id=None) # Let MaityAgent generate the ID
        _agent_instances[agent.conversation_id] = agent # Store it by its *actual generated* ID
        logger.info(f"Created and stored new MaityAgent with generated ID: {agent.conversation_id}")
        return agent

    if true_conv_id not in _agent_instances:
        logger.info(f"Creating new MaityAgent for specific conversation_id: {true_conv_id}")
        _agent_instances[true_conv_id] = MaityAgent(conversation_id=true_conv_id)
        return _agent_instances[true_conv_id]

    logger.debug(f"Reusing existing MaityAgent for conversation_id: {true_conv_id}")
    return _agent_instances[true_conv_id]
