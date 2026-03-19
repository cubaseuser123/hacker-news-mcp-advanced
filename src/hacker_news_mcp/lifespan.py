"""
Lifespan management - shared httpx.AsyncClient across all requests.
"""

import httpx 
from fastmcp.server.lifespan import lifespan

HN_ALGOLIA_BASE = "https://hn.algolia.com/api/v1"
HN_FIREBASE_BASE = "https://hacker-news.firebaseio.com/v0"

@lifespan
async def hn_lifespan(server):
    """
    Creates a shared httpx.AsyncClient on startup which will close cleanly on shutdown
    """
    async with httpx.AsyncClient(
        base_url = HN_ALGOLIA_BASE,
        timeout = httpx.Timeout(30.0),
        headers = {"User-Agent" : "hacker-news-mcp/0.1.0"},
    )as algolia_client:
        async with httpx.AsyncClient(
            base_url = HN_FIREBASE_BASE,
            timeout = httpx.Timeout(30.0),
            headers = {"User-Agent" : "hacker-news-mcp/0.1.0"},
        )as firebase_client:
            yield {
                "algolia_client": algolia_client,
                "firebase_client": firebase_client,
            }