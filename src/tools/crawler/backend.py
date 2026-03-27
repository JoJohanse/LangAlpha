"""Abstract crawler backend protocol."""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class CrawlOutput:
    """Raw output from a crawler backend."""

    title: str
    html: str
    markdown: str


class CrawlerBackend(Protocol):
    """Protocol for pluggable crawler backends."""

    async def crawl(self, url: str) -> str:
        """Crawl a URL and return markdown content."""
        ...

    async def crawl_with_metadata(self, url: str) -> CrawlOutput:
        """Crawl a URL and return full metadata."""
        ...

    async def shutdown(self) -> None:
        """Gracefully release resources."""
        ...
