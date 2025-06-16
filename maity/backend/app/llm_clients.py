import os
import enum
import openai
import anthropic
import google.generativeai as genai
import logging # Added
from . import config

logger = logging.getLogger(__name__) # Added

# --- Client Initialization ---
# Best practice: Initialize clients once
try:
    if config.OPENAI_API_KEY:
        openai.api_key = config.OPENAI_API_KEY
        logger.info("OpenAI client configured with API key.")
    else:
        logger.info("OpenAI API key not found in config. OpenAI client not explicitly configured by llm_clients.py.")
except Exception as e:
    logger.error(f"Error initializing OpenAI client: {e}", exc_info=True)

try:
    if config.ANTHROPIC_API_KEY:
        anthropic_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        logger.info("Anthropic client initialized.")
    else:
        anthropic_client = None
        logger.info("Anthropic API key not found. Anthropic client not initialized.")
except Exception as e:
    logger.error(f"Error initializing Anthropic client: {e}", exc_info=True)
    anthropic_client = None

try:
    if config.GOOGLE_API_KEY:
        genai.configure(api_key=config.GOOGLE_API_KEY)
        logger.info("Google GenAI client configured.")
    else:
        logger.info("Google API key not found. Google GenAI client not configured by llm_clients.py.")
        pass
except Exception as e:
    logger.error(f"Error initializing Google GenAI client: {e}", exc_info=True)

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
    logger.info(f"Attempting direct LLM call to model: {model_id}. Kwargs: {kwargs}")
    try:
        if model_id == ModelType.CLAUDE_37_SONNET and anthropic_client:
            logger.debug(f"Using Anthropic client for model {model_id}.")
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
            logger.debug(f"Using Google GenAI client for model {model_id}.")
            # Ensure genai was configured (i.e., GOOGLE_API_KEY was present)
            if not genai.API_KEY: # Check if API key was configured. genai.API_KEY might not be the right check.
                               # Better to rely on successful genai.configure() or raise if model init fails.
                logger.error("Google GenAI client not configured (API key likely missing). Cannot make direct call.")
                raise ValueError("Google GenAI client not configured due to missing API key.")
            model = genai.GenerativeModel(model_id)
            response = await model.generate_content_async(
                contents=messages,
                generation_config=genai.types.GenerationConfig(**kwargs)
            )
            return response.text

        elif model_id == ModelType.O3_MINI:
            logger.debug(f"Using OpenAI client for model {model_id}.")
            if not openai.api_key: # Check if API key was set
                logger.error("OpenAI client not configured (API key likely missing). Cannot make direct call.")
                raise ValueError("OpenAI client not configured due to missing API key.")
            response = await openai.chat.completions.create(
                model=model_id, messages=messages, **kwargs
            )
            return response.choices[0].message.content

        else:
            logger.warning(f"Direct call not implemented or client not available for model: {model_id}")
            raise ValueError(f"Direct call not implemented or client not available for model: {model_id}")

    except Exception as e:
        logger.error(f"Error during direct LLM call to {model_id}: {type(e).__name__} - {e}", exc_info=True)
        raise # Re-raise the exception for the caller to handle, potentially wrapped in a custom LLMCallError
