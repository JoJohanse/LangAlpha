"""Capture sandbox images from SSE events and persist to cloud storage.

At persistence time, scans message_chunk text events for sandbox-relative
image paths (e.g., work/analysis/charts/revenue.png), downloads from sandbox,
uploads to cloud storage, and rewrites the paths to storage URLs in-place.

This ensures persisted SSE events contain permanent storage URLs that render
natively on replay without sandbox access.

No-op when storage is disabled (storage.provider = "none").
"""

import asyncio
import logging
import re
import uuid

from src.utils.storage import (
    get_public_url,
    is_storage_enabled,
    upload_bytes,
)

logger = logging.getLogger(__name__)

IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "svg", "webp", "bmp"}
IMAGE_MD_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def _is_sandbox_image_path(path: str) -> bool:
    """Check if path is a sandbox-relative image (not an external URL)."""
    if path.startswith(("http://", "https://", "//", "data:")):
        return False
    normalized = path.replace("/home/daytona/", "")
    ext = normalized.rsplit(".", 1)[-1].lower() if "." in normalized else ""
    return ext in IMAGE_EXTS


async def capture_and_rewrite_images(
    sse_events: list[dict],
    sandbox,
    thread_id: str = "",
) -> int:
    """Scan SSE events for sandbox image paths, upload to storage, rewrite in-place.

    Returns number of images captured. No-op if storage is disabled.
    Non-fatal: logs warnings on failure, never raises.
    """
    if not is_storage_enabled() or not sse_events:
        return 0

    # Collect all unique sandbox image paths from text message_chunks
    image_paths: set[str] = set()
    for evt in sse_events:
        if evt.get("event") != "message_chunk":
            continue
        data = evt.get("data", {})
        if data.get("content_type") != "text":
            continue
        content = data.get("content", "")
        for match in IMAGE_MD_RE.finditer(content):
            path = match.group(2)
            if _is_sandbox_image_path(path):
                image_paths.add(path)

    if not image_paths:
        return 0

    # Download from sandbox → upload to storage → build path→URL mapping
    batch_id = uuid.uuid4().hex[:12]
    prefix = f"response-images/{thread_id}/{batch_id}" if thread_id else f"response-images/{batch_id}"
    path_to_url: dict[str, str] = {}

    for path in image_paths:
        try:
            normalized = path.replace("/home/daytona/", "")
            abs_path = sandbox.normalize_path(normalized)
            content = await sandbox.adownload_file_bytes(abs_path)
            if not content:
                continue
            # Use full relative path to avoid collisions (e.g., task1/chart.png vs task2/chart.png)
            storage_key = f"{prefix}/{normalized}"
            # upload_bytes is sync (boto3) — run in thread to avoid blocking
            success = await asyncio.to_thread(upload_bytes, storage_key, content)
            if success:
                url = get_public_url(storage_key)
                path_to_url[path] = url
                logger.info(f"[IMAGE_CAPTURE] Uploaded {path} → {storage_key}")
        except Exception as e:
            logger.warning(f"[IMAGE_CAPTURE] Failed to capture {path}: {e}")

    if not path_to_url:
        return 0

    # Rewrite image paths in SSE events in-place
    def replacer(match):
        alt, path = match.group(1), match.group(2)
        if path in path_to_url:
            return f"![{alt}]({path_to_url[path]})"
        return match.group(0)

    for evt in sse_events:
        if evt.get("event") != "message_chunk":
            continue
        data = evt.get("data", {})
        if data.get("content_type") != "text":
            continue
        content = data.get("content", "")
        if content:
            data["content"] = IMAGE_MD_RE.sub(replacer, content)

    return len(path_to_url)
