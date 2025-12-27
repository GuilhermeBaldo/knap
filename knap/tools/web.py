"""Tools for web search."""

from duckduckgo_search import DDGS

from .base import Tool, ToolResult


class WebSearchTool(Tool):
    """Search the web for information."""

    name = "web_search"
    description = (
        "Search the web for current information. Use this when you need to find "
        "up-to-date information, research topics, or answer questions that require "
        "external knowledge beyond the vault contents."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 5)",
            },
        },
        "required": ["query"],
    }

    def __init__(self) -> None:
        # No vault_path needed for web search
        pass

    def execute(self, query: str, max_results: int = 5) -> ToolResult:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))

            if not results:
                return ToolResult(
                    success=True,
                    data=[],
                    message=f"No results found for '{query}'",
                )

            # Format results
            formatted = [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                }
                for r in results
            ]

            return ToolResult(
                success=True,
                data=formatted,
                message=f"Found {len(formatted)} results for '{query}'",
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                message=f"Web search failed: {e}",
            )
