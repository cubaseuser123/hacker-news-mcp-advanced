from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
from fastmcp import FastMCP
from fastmcp.server.context import Context
from fastmcp.dependencies import CurrentContext

def register_resources(mcp: FastMCP) -> None:
    @mcp.resource(
        uri = "hn://stories/top",
        name = "TopStories",
        description = "Static snapshot of the current top 20 hacker news stories.",
        mime_type = "application/json",
        tags={"stories", "top"},
    )
    async def get_top_stories(ctx : Context = CurrentContext()) -> str:
        firebase = ctx.lifespan_context["firebase_client"]
        await ctx.info("Resource read : hn://stories/top")

        resp = await firebase.get("/topstories.json")
        resp.raise_for_status()
        story_ids = resp.json()[:20]

        stories = []
        for i, sid in enumerate(story_ids):
            await ctx.report_progress(progress = i, total = 20)
            item_resp = await firebase.get(f"/item/{sid}.json")
            item_resp.raise_for_status()
            item = item_resp.json()
            if item:
                stories.append({
                    "id" : item.get("id"),
                    "title" : item.get("title", "Untitled"),
                    "url" : item.get("url", ""),
                    "score" : item.get("score", 0),
                    "by" : item.get("by", "unknown"),
                    "descendants" : item.get("descendants", 0),
                    "time" : datetime.fromtimestamp(
                        item.get("time", 0), tz=timezone.utc
                    ).isoformat(),
                })
        await ctx.report_progress(progress = 20, total = 20)
        return json.dumps(stories, indent = 2)


    @mcp.resource(
        uri = "hn://item/{item_id}",
        name = "HNItem",
        description = "Fetch any Hacker News item (story, comment, poll, job) by its ID.",
        mime_type = 'application/json',
        tags={"item", "detail"},
    )
    async def item_resource(item_id: int, ctx: Context = CurrentContext()) -> str:
        firebase = ctx.lifespan_context["firebase_client"]

        await ctx.info(f"Resource read : hn://item/{item_id}")

        resp = await firebase.get(f"/item/{item_id}.json")
        resp.raise_for_status()
        item = resp.json()

        if not item:
            return json.dumps({"error" : f"Item {item_id} not found"})

        result = {
            "id" : item.get("id"),
            "type" : item.get("type", "unknown"),
            "title" : item.get("title", ""),
            "text" : item.get("text", ""),
            "url" : item.get("url", ""),
            "by" : item.get("by", "unknown"),
            "time" : datetime.fromtimestamp(
                item.get("time", 0), tz=timezone.utc
            ).isoformat(),
            "score" : item.get("score", 0),
            "descendants" : item.get("descendants", 0),
            "kids_count" : len(item.get("kids", [])),
        }
        return json.dumps(result, indent = 2)