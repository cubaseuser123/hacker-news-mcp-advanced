from __future__ import annotations 

import json
from datetime import datetime, timedelta, timezone

import httpx 
from fastmcp import FastMCP
from fastmcp.server.context import Context
from fastmcp.dependencies import CurrentContext

def register_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name='get_top_stories',
        description=(
            "Fetch the top N stories from Hacker News with titles, scores,"
            "URLs, authors, and comment counts."
        ),
        tags={"stories", "top"},
    )
    async def get_top_stories(
        limit: int = 10,
        ctx: Context = CurrentContext(),
    ) -> str:
        """
        Fetch the top stories from HN (default 10, max 30).
        """
        limit = min(max(1, limit), 30)

        firebase: httpx.AsyncClient = ctx.lifespan_context["firebase_client"]
        algolia: httpx.AsyncClient = ctx.lifespan_context["algolia_client"]

        await ctx.info(f"Fetching top {limit} story IDs from HN Firebase API")

        resp = await firebase.get("/topstories.json")
        resp.raise_for_status()
        story_ids: list[int] = resp.json()[:limit]

        stories = []
        total = len(story_ids)

        for i, story_id in enumerate(story_ids):
            await ctx.report_progress(progress=i, total=total)
            await ctx.debug(f"Fetching story {story_id} ({i+1}/{total})")

            item_resp = await firebase.get(f"/item/{story_id}.json")
            item_resp.raise_for_status()
            item = item_resp.json()

            if item:
                stories.append({
                    "id": item.get("id"),
                    "title": item.get("title", "untitled"),
                    "url": item.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                    "score": item.get("score", 0),
                    "by": item.get("by", "unknown"),
                    "descendants": item.get("descendants", 0),
                    "time": datetime.fromtimestamp(
                        item.get("time", 0), tz=timezone.utc
                    ).isoformat(),
                })
        
        await ctx.report_progress(progress=total, total=total)
        await ctx.info(f"Successfully fetched {len(stories)} top stories")

        return json.dumps(stories, indent=2)

    @mcp.tool(
        name="get_story_details",
        description=(
            "Fetch a single HN story by ID, including its metadata and "
            "top-level comments (up to 10)."
        ),
        tags={"stories", "details"},
    )
    async def get_story_details(
        story_id: int,
        ctx: Context = CurrentContext(),
    ) -> str:
        """
        Fetching a single story here
        """
        firebase: httpx.AsyncClient = ctx.lifespan_context["firebase_client"]

        await ctx.info(f"Fetching story details for ID {story_id}")

        resp = await firebase.get(f"/item/{story_id}.json")
        resp.raise_for_status()
        story = resp.json()

        if not story:
            return json.dumps({"error": f"Story {story_id} not found"})
        
        comment_ids = story.get("kids", [])[:10]
        comments = []
        total_comments = len(comment_ids)

        for i, cid in enumerate(comment_ids):
            await ctx.report_progress(progress=i, total=total_comments)

            comment_resp = await firebase.get(f"/item/{cid}.json")
            comment_resp.raise_for_status()
            comment = comment_resp.json()

            if comment and comment.get("type") == "comment":
                comments.append({
                    "id": comment.get("id"),
                    "by": comment.get("by", "[deleted]"),
                    "text": comment.get("text", ""),
                    "time": datetime.fromtimestamp(
                        comment.get("time", 0), tz=timezone.utc
                    ).isoformat(),
                })
            
        await ctx.report_progress(progress=total_comments, total=total_comments)
        
        result = {
            "id": story.get("id"),
            "title": story.get("title", "Untitled"),
            "url": story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
            "text": story.get("text", ""),
            "score": story.get("score", 0),
            "by": story.get("by", "unknown"),
            "descendants": story.get("descendants", 0),
            "time": datetime.fromtimestamp(
                story.get("time", 0), tz=timezone.utc
            ).isoformat(),
            "type": story.get("type", "story"),
            "comments": comments,
        }

        await ctx.info(
            f"Fetched story '{result['title']}' with {len(comments)} comments"
        )
        return json.dumps(result, indent=2)

    @mcp.tool(
        name='search_stories',
        description=(
            "Search Hacker News via the Algolia API. Supports full-text"
            "query and optional data range filtering."
        ),
        tags={"search", "algolia"},
    )
    async def search_stories(
        query: str,
        days_back: int = 7,
        limit: int = 10,
        ctx: Context = CurrentContext(),
    ) -> str:
        
        limit = min(max(1, limit), 30)
        algolia: httpx.AsyncClient = ctx.lifespan_context["algolia_client"]

        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        numeric_filters = f"created_at_i>{int(cutoff.timestamp())}"

        await ctx.info(
            f"Searching Algolia for '{query}' (last {days_back} days, limit {limit})"
        )
        resp = await algolia.get(
            "/search",
            params={
                "query": query,
                "tags": "story",
                "numericFilters": numeric_filters,
                "hitsPerPage": limit,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for hit in data.get('hits', []):
            results.append({
                "id": hit.get("objectID"),
                "title": hit.get("title", "Untitled"),
                "url": hit.get("url", ""),
                "author": hit.get("author", "unknown"),
                "points": hit.get("points", 0),
                "num_comments": hit.get("num_comments", 0),
                "created_at": hit.get("created_at", ""),
                "story_url": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
            })
        
        await ctx.info(f"Found {len(results)} results for '{query}'")
        return json.dumps(results, indent=2)

    @mcp.tool(
        name="get_user",
        description="Fetch a Hacker News user profile by username.",
        tags={"user", "profile"},
    )
    async def get_user(
        username: str,
        ctx: Context = CurrentContext(),
    ) -> str:
        
        firebase: httpx.AsyncClient = ctx.lifespan_context["firebase_client"]

        await ctx.info(f"Fetching user profile for '{username}'")

        resp = await firebase.get(f"/user/{username}.json")
        resp.raise_for_status()
        user = resp.json()

        if not user:
            return json.dumps({"error": f"User '{username}' not found"})
        
        result = {
            "id": user.get("id"),
            "created": datetime.fromtimestamp(
                user.get("created", 0), tz=timezone.utc
            ).isoformat(),
            "karma": user.get("karma", 0),
            "about": user.get("about", ""),
            "submitted_count": len(user.get("submitted", [])), 
        }

        await ctx.info(f"Found user '{username}' with {result['karma']} karma")
        return json.dumps(result, indent=2)
