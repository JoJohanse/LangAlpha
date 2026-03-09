"""
Multimodal context utilities for chat endpoint.

Parses MultimodalContext items from additional_context and injects image/PDF
content blocks into user messages so the LLM receives native multimodal input.
"""

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional

from src.server.models.additional_context import MultimodalContext
from src.utils.storage import get_public_url, is_storage_enabled, upload_base64

logger = logging.getLogger(__name__)


def parse_multimodal_contexts(
    additional_context: Optional[List[Any]],
) -> List[MultimodalContext]:
    """Extract MultimodalContext items from additional_context list.

    Args:
        additional_context: List of context items from ChatRequest

    Returns:
        List of MultimodalContext objects
    """
    if not additional_context:
        return []

    contexts = []

    for ctx in additional_context:
        if isinstance(ctx, dict):
            if ctx.get("type") == "image":
                contexts.append(
                    MultimodalContext(
                        type="image",
                        data=ctx.get("data", ""),
                        description=ctx.get("description"),
                    )
                )
        elif isinstance(ctx, MultimodalContext):
            contexts.append(ctx)
        elif hasattr(ctx, "type") and ctx.type == "image":
            contexts.append(
                MultimodalContext(
                    type="image",
                    data=getattr(ctx, "data", ""),
                    description=getattr(ctx, "description", None),
                )
            )

    return contexts


async def build_attachment_metadata(
    contexts: List[MultimodalContext],
    thread_id: str = "",
) -> List[Dict[str, Any]]:
    """Build attachment metadata dicts, uploading to storage when enabled.

    Returns list of {name, type, size, url?} dicts.
    Uploads run concurrently via asyncio.gather.
    """
    batch_id = uuid.uuid4().hex[:12]
    prefix = f"attachments/{thread_id}/{batch_id}" if thread_id else f"attachments/{batch_id}"

    async def _process(ctx: MultimodalContext) -> Dict[str, Any]:
        is_pdf = ctx.data.startswith("data:application/pdf")
        name = ctx.description or "file"
        meta: Dict[str, Any] = {
            "name": name,
            "type": "pdf" if is_pdf else "image",
            "size": len(ctx.data.split(",", 1)[1]) * 3 // 4 if "," in ctx.data else 0,
        }
        if is_storage_enabled():
            try:
                storage_key = f"{prefix}/{name}"
                success = await asyncio.to_thread(upload_base64, storage_key, ctx.data)
                if success:
                    meta["url"] = get_public_url(storage_key)
            except Exception:
                logger.warning(f"Failed to upload attachment {name}", exc_info=True)
        return meta

    return list(await asyncio.gather(*(_process(ctx) for ctx in contexts)))


def inject_multimodal_context(
    messages: List[Dict[str, Any]],
    multimodal_contexts: List[MultimodalContext],
) -> List[Dict[str, Any]]:
    """Inject a separate context message with image/PDF content before the user query.

    Inserts a new user message containing the attachment(s) right before the last
    user message, so the LLM sees the visual/document context first and the user's
    question second.

    Args:
        messages: List of message dicts (role + content)
        multimodal_contexts: List of MultimodalContext objects to inject

    Returns:
        Modified messages list with context message inserted
    """
    if not multimodal_contexts or not messages:
        return messages

    # Build the context message content blocks
    blocks: List[Dict[str, Any]] = []
    for ctx in multimodal_contexts:
        data_url = ctx.data
        desc = ctx.description or "file"

        if data_url.startswith("data:application/pdf"):
            # PDF: extract raw base64 and use file content block
            raw_b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
            blocks.append({"type": "text", "text": f"[Attached PDF: {desc}]"})
            blocks.append({
                "type": "file",
                "base64": raw_b64,
                "mime_type": "application/pdf",
                "filename": desc,
            })
        else:
            # Image: use correct nested image_url format
            blocks.append({"type": "text", "text": f"[Attached image: {desc}]"})
            blocks.append({"type": "image_url", "image_url": {"url": data_url}})

    if not blocks:
        return messages

    context_message = {"role": "user", "content": blocks}

    # Insert before the last user message
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            messages.insert(i, context_message)
            break

    return messages
