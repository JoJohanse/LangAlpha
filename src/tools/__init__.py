
from .crawl import crawl_tool
from .fetch import web_fetch_tool, web_fetch

# Backwards compatibility: re-export from new location
from ptc_agent.agent.tools.todo import TodoWrite


def get_web_search_tool(*args, **kwargs):
    from .search import get_web_search_tool as _get_web_search_tool

    return _get_web_search_tool(*args, **kwargs)


def get_research_tool(*args, **kwargs):
    from .search import get_research_tool as _get_research_tool

    return _get_research_tool(*args, **kwargs)


__all__ = [
    "crawl_tool",
    "web_fetch_tool",
    "web_fetch",
    "get_web_search_tool",
    "get_research_tool",
    "TodoWrite",
]
