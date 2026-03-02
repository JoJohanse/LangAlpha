"""Shared parser for Tavily Research API SSE streams."""

import json
from typing import List, Optional, Tuple


async def parse_research_stream(
    stream,
) -> Tuple[str, List[dict], Optional[str]]:
    """Parse a Tavily research SSE stream into (content, sources, resolved_model).

    Args:
        stream: Async generator of SSE byte/string chunks from
                client.research(stream=True)

    Returns:
        Tuple of (assembled_content, sources_list, resolved_model_name)
    """
    content_parts: list[str] = []
    sources: list[dict] = []
    resolved_model: Optional[str] = None
    buffer = ""

    async for chunk in stream:
        text = chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk)
        buffer += text
        *lines, buffer = buffer.split("\n")

        for line in lines:
            if not line.startswith("data: "):
                continue
            try:
                data = json.loads(line[6:])
            except json.JSONDecodeError:
                continue

            # Capture model from first event (resolves 'auto')
            if event_model := data.get("model"):
                resolved_model = event_model

            choices = data.get("choices")
            if not choices:
                continue
            delta = choices[0].get("delta", {})

            if "content" in delta:
                c = delta["content"]
                if isinstance(c, dict):
                    # output_schema mode: entire structured result in one chunk
                    content_parts.append(json.dumps(c))
                elif isinstance(c, str):
                    content_parts.append(c)
            if "sources" in delta:
                sources = delta["sources"]

    return "".join(content_parts), sources, resolved_model
