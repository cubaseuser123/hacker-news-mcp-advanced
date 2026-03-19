from __future__ import annotations
import sys 
from fastmcp import FastMCP
from hacker_news_mcp.lifespan import hn_lifespan
from hacker_news_mcp.tools import register_tools
from hacker_news_mcp.resources import register_resources
from hacker_news_mcp.prompts import register_prompts

mcp = FastMCP(
    name = 'hacker-news-mcp',
    instructions = (
        "A Hacker News MCP server. Use the provided tools to fetch stories, "
        "search HN, and get user profiles. Use the hn_digest prompt for a "
        "curated daily briefing."
    ),
    lifespan = hn_lifespan,
)

register_tools(mcp)
register_resources(mcp)
register_prompts(mcp)

def main():
    if "--http" in sys.argv:
        mcp.run(
            transport="streamable-http",
            host="127.0.0.1",
            port=8000,
            path="/mcp",
        )
    else:
        mcp.run(transport='stdio')

if __name__ == "__main__":
    main()