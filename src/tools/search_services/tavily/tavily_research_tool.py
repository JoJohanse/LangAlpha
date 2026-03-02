"""Tavily research tool for deep research via LangChain integration."""

import json
import logging
from typing import Any, Dict, Optional, Tuple

from langchain_core.tools import tool

from src.tools.search_services.tavily.tavily_search_api_wrapper import (
    TavilySearchWrapper,
)

logger = logging.getLogger(__name__)

# Module-level configuration
_api_wrapper: Optional[TavilySearchWrapper] = None
_verbose: bool = True
_model: str = "auto"


def configure(
    verbose: bool = True,
    model: str = "auto",
) -> None:
    """Configure the Tavily research tool settings.

    Args:
        verbose: Control verbosity of research results.
        model: Research model - 'mini' (faster, cheaper), 'pro' (deeper, more
            thorough), or 'auto' (system decides based on query complexity).
    """
    global _api_wrapper, _verbose, _model

    _verbose = verbose
    _model = model
    _api_wrapper = None  # Reset wrapper to pick up new config


def _get_api_wrapper() -> TavilySearchWrapper:
    """Get or create the API wrapper instance."""
    global _api_wrapper
    if _api_wrapper is None:
        _api_wrapper = TavilySearchWrapper()
    return _api_wrapper


@tool(response_format="content_and_artifact")
async def deep_research(
    description: str,
    instruction: str,
) -> Tuple[str, Dict[str, Any]]:
    """Perform deep research on a topic to generate a comprehensive report.

    Unlike web search which returns individual results, this performs multi-step
    research across many sources and synthesizes a detailed report. Use for:
    - In-depth analysis of complex topics
    - Comprehensive literature reviews
    - Multi-faceted research questions requiring synthesis

    This is a long-running operation (may take 30-60+ seconds).

    Args:
        description: Brief one-line description of the research goal for display
        instruction: Detailed research instruction specifying what to investigate,
            what aspects to cover, and what format the report should take
    """
    try:
        api = _get_api_wrapper()
        client = api._client

        # Use streaming to avoid manual polling — the SDK async generator
        # handles waiting internally and yields SSE chunks as they arrive.
        stream = await client.research(input=instruction, model=_model, stream=True)

        content_parts = []
        sources = []
        actual_model = _model

        async for chunk in stream:
            text = chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk)

            for line in text.strip().split("\n"):
                if not line.startswith("data: "):
                    continue
                try:
                    data = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue

                # Capture model from first event (resolves 'auto')
                if event_model := data.get("model"):
                    actual_model = event_model

                choices = data.get("choices")
                if not choices:
                    continue
                delta = choices[0].get("delta", {})

                if "content" in delta:
                    content_parts.append(delta["content"])
                if "sources" in delta:
                    sources = delta["sources"]

        content = "".join(content_parts)
        logger.info(
            f"Tavily research completed: model={actual_model}, "
            f"content_len={len(content)}, sources={len(sources)}"
        )

        # Dynamic credit tracking based on actual model used
        from src.tools.decorators import get_tool_tracker

        tracker = get_tool_tracker()
        if tracker:
            if actual_model == "pro":
                tracker.record_usage("TavilyResearchPro")
            else:
                tracker.record_usage("TavilyResearchMini")

        artifact = {
            "type": "research",
            "description": description,
            "model": actual_model,
            "sources": sources,
        }

        return content, artifact

    except Exception as e:
        logger.error(f"Tavily research failed: {e}", exc_info=True)
        return repr(e), {"error": str(e), "description": description}
