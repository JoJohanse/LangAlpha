"""Get preview URLs for services running in the sandbox."""

from typing import Any

import structlog
from langchain_core.tools import BaseTool, tool

logger = structlog.get_logger(__name__)


def create_preview_url_tool(sandbox: Any) -> BaseTool:
    """Factory function to create GetPreviewUrl tool with injected dependencies.

    Args:
        sandbox: PTCSandbox instance for preview URL generation

    Returns:
        Configured GetPreviewUrl tool function
    """

    @tool
    async def GetPreviewUrl(
        port: int,
        title: str | None = None,
    ) -> str:
        """Get a preview URL for a service running on the given port in the sandbox.

        Use this after starting a web server or frontend dev server in the background
        to generate a URL that the user can view in the preview panel.

        Args:
            port: Port number (3000-9999) the service is listening on
            title: Optional display title for the preview (default: "Port {port}")

        Returns:
            The signed preview URL that can be used to access the service
        """
        try:
            from langgraph.config import get_stream_writer

            writer = get_stream_writer()
        except Exception:
            writer = None

        try:
            preview_info = await sandbox.get_preview_url(port, expires_in=3600)
            url = preview_info.url
            display_title = title or f"Port {port}"

            logger.info(
                "Generated preview URL",
                port=port,
                title=display_title,
                url=url[:80],
            )

            # Emit SSE artifact so the frontend can open the preview panel
            if writer:
                writer({
                    "artifact_type": "preview_url",
                    "artifact_id": f"preview_{port}",
                    "payload": {
                        "url": url,
                        "port": port,
                        "title": display_title,
                    },
                })

            return f"Preview URL for {display_title}: {url}"

        except NotImplementedError:
            return "ERROR: Preview URLs are not supported by the current sandbox provider"
        except Exception as e:
            error_msg = f"Failed to generate preview URL for port {port}: {e!s}"
            logger.error(error_msg, port=port, error=str(e), exc_info=True)
            return f"ERROR: {error_msg}"

    return GetPreviewUrl
