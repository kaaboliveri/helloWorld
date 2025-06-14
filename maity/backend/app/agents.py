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

        # --- Conceptual Enhancements for Model Selection ---
        # 1. Task Complexity Analysis:
        #    - Before choosing a model, analyze the user's message and conversation history.
        #    - If the task seems simple (e.g., quick question, summarization of short text),
        #      a faster/cheaper model like o3-mini might be sufficient even if not preferred.
        #    - If complex (e.g., coding, deep research, app generation request), a more powerful
        #      model (Claude 3.7, Gemini 2.5 Pro) should be prioritized.
        #    - This could involve a preliminary LLM call to classify task complexity or keyword heuristics.
        # 2. Tool-Specific Model Overrides:
        #    - Some tools might inherently benefit from specific models. E.g., `generate_app_tool`
        #      might always default to Gemini 2.5 Pro or Claude 3.7 Sonnet for its internal planning/codegen steps,
        #      regardless of the user's general preference for the main chat interaction.
        #    - The agent could maintain a mapping of (tool_name -> preferred_model_for_tool_use).
        # 3. Cost/Benefit Analysis (Very Advanced):
        #    - If multiple models could do the job, factor in relative costs and typical performance
        #      for the type of task. (Requires up-to-date knowledge of model pricing/capabilities).

        selected_model_id = preferred_model or ModelType.CLAUDE_37_SONNET.value
        model_config = get_model_configuration(selected_model_id)
        print(f"Selected model for main interaction: {selected_model_id}")

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
        # ... (final_output, tool_calls_info, error_occurred, debug_info initialization) ...
        debug_info = {"model_used": selected_model_id, "tool_calls": []} # Ensure tool_calls is initialized

        try:
            # --- Conceptual Enhancements for Agent's Internal Planning & Tool Use (within SDK's scope) ---
            # The OpenAI Agents SDK's `Runner` handles the primary loop of thought, tool choice, observation.
            # Enhancements here are more about how *this MaityAgent class* interacts with or configures the SDK Agent.
            # 1. Pre-computation/Contextual Priming for Runner:
            #    - Before `runner.run()`, if the task clearly implies a specific tool (e.g., user says "generate an app about X"),
            #      could we somehow prime the SDK Agent or provide stronger initial instructions/context
            #      to guide its first few steps? (Depends on SDK capabilities).
            # 2. Dynamic Tool Enablement/Disablement (Advanced):
            #    - Based on conversation context or user permissions (if implemented),
            #      dynamically adjust the list of `ALL_TOOLS` passed to the `Agent` constructor.
            #      E.g., disable `execute_code_tool` if the user is in a restricted mode.
            # 3. Iterative Refinement with User for Complex Tasks:
            #    - For tools like `generate_app_tool`, the first call might produce a plan.
            #    - The agent could present this plan to the user for confirmation/modification
            #      *before* proceeding with the full generation. This involves yielding control,
            #      getting user feedback, and then re-running the agent/tool with updated instructions.
            #      (This is a complex control flow beyond a single `runner.run()`.)

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
            response_content = f"(Agent error: {error_msg})" # Keep it simple for user
            self._add_message("assistant", response_content)
            # error_occurred = True # Ensure this is set if used
            debug_info["error"] = error_msg

            # --- Conceptual Enhancements for Tool Error Handling & Recovery ---
            # 1. Error Classification:
            #    - Is the error transient (e.g., network hiccup, API rate limit)? -> Retry.
            #    - Is it due to bad input arguments from the LLM for the tool? -> Re-prompt LLM with error context.
            #    - Is it a fatal tool error (e.g., tool misconfiguration, sandbox issue)? -> Inform user, maybe suggest alternative.
            # 2. Retry Logic for Tools:
            #    - For some tools (e.g., web_search_tool on network error), a simple retry (1-2 times) might work.
            #    - This would require catching specific exceptions or error messages.
            # 3. Re-Prompting LLM on Bad Tool Input:
            #    - If ToolError indicates LLM provided invalid arguments (e.g., wrong format, missing required arg):
            #      `new_prompt = f"Your previous attempt to use {e.tool_name} failed because: {e.message}.
            #                     The required arguments are: {tool_schema}. Please try again with correct arguments."`
            #      Then, re-run the agent loop with this new instruction added to history. (Complexifies state).
            # 4. Asking User for Clarification:
            #    - If a tool fails consistently or the agent can't determine how to fix its input:
            #      `response_content = f"I tried to use {e.tool_name} but encountered an issue: {e.message}.
            #                         Could you please clarify X or try rephrasing your request?"`

        except HandoffRefusalError as e: # Assuming this is from openai-agents SDK
            # ... (existing HandoffRefusalError handling) ...
            error_msg = f"Agent refused to hand off: {e}"
            print(error_msg)
            response_content = f"(Agent error: {error_msg})"
            self._add_message("assistant", response_content)
            debug_info["error"] = error_msg

        except Exception as e:
            # ... (existing generic Exception handling) ...
            error_msg = f"An unexpected error occurred in agent: {type(e).__name__} - {str(e)}"
            print(error_msg)
            # For user, a generic message is often better unless it's a known, actionable issue
            response_content = f"(System error: I encountered an issue. Please try again or rephrase.)"
            # self._add_message("assistant", response_content) # Decide if this detailed error goes to history
            debug_info["error"] = error_msg # Log detailed error for debugging
            # Add a generic message to history for the user
            if not any(m['role'] == 'assistant' and m['content'] == response_content for m in self._get_history()[-2:]): # Avoid duplicate generic errors
                 self._add_message("assistant", "I encountered an unexpected issue. Please try rephrasing your request or try again later.")


        return {
            "content": response_content,
            "conversation_id": self.conversation_id,
            "error": bool(debug_info.get("error")), # Simplified error reporting
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
