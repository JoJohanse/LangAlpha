"""
Multimodal context utilities for chat endpoint.

Parses MultimodalContext items from additional_context and injects image/PDF
content blocks into user messages so the LLM receives native multimodal input.
"""

import asyncio
import base64
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from src.server.models.additional_context import MultimodalContext
from src.utils.storage import get_public_url, is_storage_enabled, sanitize_storage_key, upload_base64

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
            safe_key = sanitize_storage_key(name, ctx.data)
            storage_key = f"{prefix}/{safe_key}"
            try:
                success = await asyncio.to_thread(upload_base64, storage_key, ctx.data)
                if success:
                    meta["url"] = get_public_url(storage_key)
            except Exception:
                logger.warning("Failed to upload attachment %r", safe_key, exc_info=True)
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


# -- Unsupported-attachment reminder -----------------------------------------

_UNSUPPORTED_AGENT_INSTRUCTION = (
    "You cannot view the attached file(s) directly because the current model "
    "does not support this input type. Be transparent with the user about this "
    "limitation and suggest they try switching to a model that supports these "
    "input types (e.g. one with vision/PDF support). Work in best effort to "
    "answer the user's query."
)


def build_unsupported_reminder(notes: list[str]) -> str:
    """Build a ``<system-reminder>`` for unsupported attachments.

    Wraps one or more file-description *notes* with standard agent
    instructions, matching the ``build_directive_reminder`` pattern.

    Args:
        notes: Per-file descriptions (e.g. from ``upload_unsupported_to_sandbox``
            or a simple type summary for Flash mode).

    Returns:
        Formatted ``<system-reminder>`` string ready for
        ``_append_to_last_user_message``.
    """
    body = "\n".join(notes)
    return (
        "\n\n<system-reminder>\n"
        f"{body}\n"
        f"{_UNSUPPORTED_AGENT_INSTRUCTION}\n"
        "</system-reminder>"
    )


# -- Capability-aware helpers ------------------------------------------------

# Mapping from MIME type prefix to file extension
_MIME_EXTENSIONS = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
}


def filter_multimodal_by_capability(
    contexts: list,
    modalities: list[str],
) -> Tuple[list, list]:
    """Filter multimodal contexts by model capabilities.

    Each context item is classified as needing either ``"pdf"`` or ``"image"``
    support.  Items whose required modality is present in *modalities* go into
    the *supported* list; the rest go into *unsupported*.

    Args:
        contexts: List of MultimodalContext objects (or dicts with a ``data`` key).
        modalities: List of modality strings the model supports (e.g.
            ``["text", "image", "pdf"]``).

    Returns:
        Tuple of (supported_contexts, unsupported_contexts).
    """
    supported: list = []
    unsupported: list = []
    for ctx in contexts:
        data = ctx.data if hasattr(ctx, "data") else ctx.get("data", "")
        needed = "pdf" if data.startswith("data:application/pdf") else "image"
        if needed in modalities:
            supported.append(ctx)
        else:
            unsupported.append(ctx)
    return supported, unsupported


async def upload_unsupported_to_sandbox(
    unsupported: list,
    sandbox,
    upload_dir: str = "uploads",
) -> List[str]:
    """Upload unsupported multimodal files to the sandbox filesystem.

    For each context item the base64 payload is decoded and written into the
    sandbox's ``work/{upload_dir}/`` directory.  A list of human-readable notes
    describing the uploaded files is returned so the caller can inject them as
    user messages.

    Args:
        unsupported: List of MultimodalContext objects that the model cannot
            handle natively.
        sandbox: The sandbox instance (must expose ``aupload_file_bytes`` and
            ``normalize_path``).
        upload_dir: Sub-directory under ``work/`` to store uploads.

    Returns:
        List of descriptive notes (one per context item).
    """
    notes: List[str] = []

    for ctx in unsupported:
        data_url = ctx.data if hasattr(ctx, "data") else ctx.get("data", "")
        desc = (
            ctx.description if hasattr(ctx, "description") else ctx.get("description")
        ) or "file"

        try:
            # Parse data URL: data:<mime>;base64,<content>
            header, b64_content = data_url.split(",", 1)
            # header looks like "data:image/png;base64"
            mime_type = header.split(":")[1].split(";")[0] if ":" in header else ""

            file_bytes = base64.b64decode(b64_content)

            # Build a unique filename
            ext = _MIME_EXTENSIONS.get(mime_type, "")
            unique_id = uuid.uuid4().hex[:8]
            # Sanitise description for use in filename
            safe_desc = "".join(
                c if c.isalnum() or c in "-_." else "_" for c in desc
            ).strip("_")[:60]
            filename = f"{safe_desc}_{unique_id}{ext}" if safe_desc else f"{unique_id}{ext}"

            rel_path = f"work/{upload_dir}/{filename}"
            abs_path = sandbox.normalize_path(rel_path)

            ok = await sandbox.aupload_file_bytes(abs_path, file_bytes)
            if not ok:
                raise RuntimeError("upload returned False")

            # Build descriptive note (file facts only — agent instructions
            # are added by build_unsupported_reminder in the caller).
            # Use virtualize_path so the note shows the path the agent
            # would use in read_file / execute_code.
            if hasattr(sandbox, "virtualize_path"):
                sandbox_display_path = sandbox.virtualize_path(abs_path)
            else:
                sandbox_display_path = abs_path
            is_pdf = mime_type == "application/pdf"
            if is_pdf:
                notes.append(
                    f"The user attached a PDF file ({desc}). "
                    f"It has been saved to {sandbox_display_path}. "
                    f"Use Python to read it (e.g., PyMuPDF, pdfplumber)."
                )
            else:
                notes.append(
                    f"The user attached an image file ({desc}). "
                    f"It has been saved to {sandbox_display_path}. "
                    f"Use Python to process it (e.g., PIL/Pillow for metadata)."
                )

        except Exception:
            logger.warning(
                f"Failed to upload unsupported attachment '{desc}' to sandbox",
                exc_info=True,
            )
            notes.append(
                "The user attached a file but it could not be uploaded to "
                "the sandbox."
            )

    return notes
