import os
import enum
import openai
import anthropic
import google.generativeai as genai
from . import config

# --- Client Initialization ---
# Best practice: Initialize clients once
try:
    if config.OPENAI_API_KEY:
        openai.api_key = config.OPENAI_API_KEY
    # Note: openai-agents SDK might handle client creation internally based on model string.
    # This explicit client might be used for calls *outside* the agent loop.
except Exception as e:
    print(f"Error initializing OpenAI client: {e}")

try:
    if config.ANTHROPIC_API_KEY:
        anthropic_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    else:
        anthropic_client = None
except Exception as e:
    print(f"Error initializing Anthropic client: {e}")
    anthropic_client = None

try:
    if config.GOOGLE_API_KEY:
        genai.configure(api_key=config.GOOGLE_API_KEY)
        # Check if model exists upon initialization or lazily
        # gemini_pro_model = genai.GenerativeModel(config.GEMINI_25_PRO_MODEL_ID)
    else:
        # gemini_pro_model = None # Cannot initialize without key
        pass # SDK might handle key later or raise error
except Exception as e:
    print(f"Error initializing Google GenAI client: {e}")
    # gemini_pro_model = None

class ModelType(str, enum.Enum):
    O3_MINI = config.O3_MINI_MODEL_ID
    CLAUDE_37_SONNET = config.CLAUDE_37_SONNET_MODEL_ID
    GEMINI_25_PRO = config.GEMINI_25_PRO_MODEL_ID

# --- SDK Integration Helper (Conceptual) ---
# The openai-agents SDK likely handles LLM calls internally.
# This function shows how you *might* configure it if needed,
# or how you'd call LLMs directly *outside* the agent loop.

def get_model_configuration(model_id: str) -> dict:
    """Returns configuration details for a given model ID."""
    if model_id == ModelType.CLAUDE_37_SONNET:
        return {
            "provider": "anthropic",
            "model_name": model_id,
            "client": anthropic_client, # May not be needed if SDK handles it
            "default_params": {
                "max_tokens": 4096,
                # Pass thinking budget via model_settings in Agent/Runner
                "thinking": {"budget_ms": config.CLAUDE_THINKING_BUDGET_MS}
            }
        }
    elif model_id == ModelType.GEMINI_25_PRO:
         return {
            "provider": "google",
            "model_name": model_id,
            # SDK likely uses google-generativeai library directly
            "default_params": {
                 "temperature": 0.7 # Example
                 # Add other Gemini specific params
            }
         }
    elif model_id == ModelType.O3_MINI:
        return {
            "provider": "openai",
            "model_name": model_id, # Use the actual model ID
            # SDK uses openai library directly
             "default_params": {
                 "temperature": 0.7 # Example
             }
        }
    else:
        raise ValueError(f"Unsupported model ID for configuration: {model_id}")

# --- Direct Call Example (If needed outside Agent SDK) ---
# This is less likely needed if using the SDK correctly, but illustrative.
async def direct_llm_call(messages: list, model_id: str, **kwargs):
    """Example of directly calling an LLM API (use with caution)."""
    print(f"Attempting direct call to model: {model_id}")
    try:
        if model_id == ModelType.CLAUDE_37_SONNET and anthropic_client:
            system_prompt = next((m['content'] for m in messages if m['role'] == 'system'), None)
            user_messages = [m for m in messages if m['role'] != 'system']
            response = await anthropic_client.messages.create(
                model=model_id,
                system=system_prompt,
                messages=user_messages,
                max_tokens=kwargs.get('max_tokens', 4096),
                thinking=kwargs.get('thinking', {"budget_ms": config.CLAUDE_THINKING_BUDGET_MS})
            )
            # Handle potential list of content blocks
            return "".join([block.text for block in response.content if hasattr(block, 'text')])
        elif model_id == ModelType.GEMINI_25_PRO:
            # Needs google-generativeai client configured
            model = genai.GenerativeModel(model_id)
            # Convert messages format if needed by google library
            # Handle potential content filtering/blocking
            response = await model.generate_content_async(
                contents=messages, # Adjust format as needed
                generation_config=genai.types.GenerationConfig(**kwargs)
            )
            return response.text
        elif model_id == ModelType.O3_MINI:
             # Needs openai client configured
             response = await openai.chat.completions.create(
                model=model_id, messages=messages, **kwargs
             )
             return response.choices[0].message.content
        else:
            raise ValueError(f"Direct call not implemented or client not available for model: {model_id}")
    except Exception as e:
        print(f"Error during direct LLM call to {model_id}: {e}")
        # Consider more specific error handling (API errors, connection errors, etc.)
        raise # Re-raise the exception for the caller to handle
