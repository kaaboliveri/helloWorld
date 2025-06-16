import asyncio
from openai_agents.tool import tool, ToolError
from playwright.async_api import async_playwright
import logging # Added
# Import necessary LLM client functions and ModelType
from ..llm_clients import direct_llm_call, ModelType, get_model_configuration

logger = logging.getLogger(__name__) # Added

_playwright = None
_browser = None

async def get_browser():
    global _playwright, _browser
    if _browser is None:
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(headless=True)
    return _browser

async def close_browser():
    global _playwright, _browser
    if _browser:
        await _browser.close()
        _browser = None
    if _playwright:
        await _playwright.stop()
        _playwright = None

@tool("Performs a web search using DuckDuckGo and returns relevant results.")
async def web_search_tool(query: str) -> str:
    logger.info(f"Executing web_search_tool with query: '{query}'")
    browser = await get_browser()
    page = await browser.new_page()
    results = []
    try:
        await page.goto(f"https://duckduckgo.com/?q={query}&ia=web")
        await page.wait_for_selector(".result__a", timeout=10000)
        result_elements = await page.query_selector_all(".result")
        for i, element in enumerate(result_elements[:5]):
            title_element = await element.query_selector(".result__a")
            snippet_element = await element.query_selector(".result__snippet")
            url = await title_element.get_attribute("href") if title_element else "N/A"
            title = await title_element.inner_text() if title_element else "N/A"
            snippet = await snippet_element.inner_text() if snippet_element else "N/A"
            results.append(f"Result {i+1}:\nTitle: {title}\nURL: {url}\nSnippet: {snippet}\n---")
        return "\n".join(results) if results else "No search results found."
    except Exception as e:
        logger.error(f"Error during web search for query '{query}': {e}", exc_info=True)
        raise ToolError(tool_name="web_search_tool", message=f"Failed to perform search: {str(e)}")
    finally:
        if page and not page.is_closed(): await page.close()

@tool("Navigates to a URL and extracts information or performs actions based on a task description.")
async def browse_website_tool(url: str, task_description: str) -> str:
    logger.info(f"Executing browse_website_tool for URL: '{url}' with task: '{task_description}'")

    browser = await get_browser()
    page = await browser.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000) # Increased timeout

        # Attempt to extract main content text using Playwright's evaluate method or selectors
        # This can be more robust than just body.inner_text() for complex pages
        try:
            # Try to get main article content or a significant portion of the body
            page_text = await page.evaluate('''() => {
                const main = document.querySelector('main article, article, main, [role="main"]');
                if (main) return main.innerText;
                return document.body.innerText;
            }''')
        except Exception as e:
            logger.warning(f"Could not extract main text via JS for URL '{url}', falling back to body text. Error: {e}", exc_info=True)
            page_text = await page.locator('body').inner_text(timeout=10000)

        # Limit text length
        # PRD mentioned Claude 3.7 Sonnet has 200K context, Gemini 2.5 Pro up to 8M (or 1M for text)
        # Let's pick a reasonable limit for now, e.g. 50k characters, which is roughly 10k-15k tokens.
        max_len = 50000
        if len(page_text) > max_len:
            page_text = page_text[:max_len] + "... (truncated due to length)"

        if not page_text.strip():
            return f"Successfully navigated to {url}, but no significant text content could be extracted."

        # --- LLM Call to process content based on task_description ---
        # Choose a model suitable for this kind of task (e.g., Claude Sonnet or Gemini Pro)
        # ModelType.CLAUDE_37_SONNET or ModelType.GEMINI_25_PRO
        processing_model_id = ModelType.CLAUDE_37_SONNET.value

        llm_prompt_messages = [
            {"role": "user", "content": f"""
            Analyze the following text content extracted from the website: {url}
            Perform the following task: "{task_description}"

            Extracted text:
            ---
            {page_text}
            ---

            Based *only* on the provided text, provide a concise answer for the task.
            If the information is not found in the text, state that clearly.
            Do not make assumptions or use external knowledge.
            """}
        ]

        logger.info(f"Sending content from '{url}' to LLM ({processing_model_id}) for task: '{task_description}'")

        try:
            model_config = get_model_configuration(processing_model_id)
            llm_params = model_config.get("default_params", {})

            # Ensure thinking parameter is correctly formatted if it exists
            # This check might be overly specific if direct_llm_call handles various formats
            if "thinking" in llm_params and isinstance(llm_params["thinking"], int): # Assuming it could be just budget_ms
                llm_params["thinking"] = {"budget_ms": llm_params["thinking"]}
            elif "thinking" in llm_params and isinstance(llm_params["thinking"], dict) and "budget_ms" not in llm_params["thinking"]:
                 # If 'thinking' is a dict but not in the expected format, try to adapt or warn
                 # For now, let's assume get_model_configuration returns it in the correct dict format if it's a dict.
                 pass


            extracted_info = await direct_llm_call(
                messages=llm_prompt_messages,
                model_id=processing_model_id,
                **llm_params
            )

            logger.info(f"LLM response for browse_website_tool (URL: '{url}', first 100 chars): {extracted_info[:100] if extracted_info else 'Empty response'}...")

            if not extracted_info or not extracted_info.strip():
                 logger.warning(f"LLM returned empty response for URL '{url}' and task '{task_description}'.")
                 return f"Successfully navigated to {url} and an LLM processed its content for task '{task_description}', but the LLM returned an empty response."

            return f"Analysis of {url} for task '{task_description}':\n{extracted_info}"

        except Exception as llm_error:
            logger.error(f"Error during LLM call in browse_website_tool for URL '{url}': {llm_error}", exc_info=True)
            raise ToolError(tool_name="browse_website_tool", message=f"Failed to process content from {url} using LLM: {str(llm_error)}")

    except Exception as e:
        logger.error(f"Error during website browse for URL '{url}': {e}", exc_info=True)
        if "net::ERR_NAME_NOT_RESOLVED" in str(e) or "Timeout" in str(e):
             raise ToolError(tool_name="browse_website_tool", message=f"Failed to navigate to {url}. It might be unreachable, invalid, or timed out.")
        raise ToolError(tool_name="browse_website_tool", message=f"Failed to browse or process {url}: {str(e)}")
    finally:
        if page and not page.is_closed():
            await page.close()
