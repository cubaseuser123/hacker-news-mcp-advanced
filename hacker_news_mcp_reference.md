# 🔶 hacker-news-mcp — Complete Code Reference (FastMCP 3.0)

> A FastMCP **3.0** Python MCP server that lets Claude interact with **Hacker News** via the public Algolia API.
> Built with `fastmcp>=3.0`, `httpx`, `uv`, Python 3.11+.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [FastMCP 3.0 — What Changed](#2-fastmcp-30--what-changed)
3. [Installation & Project Init](#3-installation--project-init)
4. [Folder Structure](#4-folder-structure)
5. [pyproject.toml](#5-pyprojecttoml)
6. [Lifespan & Shared Client](#6-lifespan--shared-client)
7. [Tools Module](#7-tools-module)
8. [Resources Module](#8-resources-module)
9. [Prompts Module](#9-prompts-module)
10. [Server Entry Point](#10-server-entry-point)
11. [Claude Desktop Config](#11-claude-desktop-config)
12. [Running the Server](#12-running-the-server)
13. [Testing & Verification](#13-testing--verification)
14. [README.md](#14-readmemd)

---

## 1. Prerequisites

| Tool     | Version  | Install                                       |
| -------- | -------- | --------------------------------------------- |
| Python   | ≥ 3.11   | [python.org](https://python.org)              |
| uv       | latest   | `pip install uv` or `pipx install uv`         |
| fastmcp  | ≥ 3.0.0  | auto-installed via `uv`                       |
| httpx    | ≥ 0.27   | auto-installed via `uv`                       |

**No API keys needed** — the HN Algolia API is fully public.

---

## 2. FastMCP 3.0 — What Changed

> [!IMPORTANT]
> This reference uses **FastMCP 3.0** patterns throughout. If you're coming from 2.x,
> here are the key differences baked into every file:

| Area | FastMCP 2.x | FastMCP 3.0 (this guide) |
| --- | --- | --- |
| **Context injection** | `ctx: Context = Context` sentinel | `ctx: Context = CurrentContext()` from `fastmcp.dependencies` |
| **Server config** | `FastMCP("name", host=..., port=...)` | `FastMCP("name")` + `mcp.run(transport=..., host=..., port=...)` |
| **Duplicate handling** | `on_duplicate_tools=...` etc. | Single `on_duplicate=...` parameter |
| **Prompts** | Accepted raw dicts | Must use `Message` from `fastmcp.prompts` |
| **State methods** | `ctx.set_state()` sync | `await ctx.set_state()` async |
| **Meta key** | `_fastmcp` | `fastmcp` |
| **Tools** | Decorators replaced the function | Decorated functions remain callable |

---

## 3. Installation & Project Init

```powershell
# 1. Create and enter project directory
mkdir hacker-news-mcp
cd hacker-news-mcp

# 2. Initialize with uv
uv init

# 3. Set Python version
echo 3.11 > .python-version

# 4. Add dependencies (fastmcp 3.0+)
uv add "fastmcp>=3.0.0" httpx

# 5. Verify installation
uv run python -c "import fastmcp; print(fastmcp.__version__)"
```

---

## 4. Folder Structure

```
hacker-news-mcp/
├── pyproject.toml           # project metadata + dependencies
├── .python-version          # 3.11
├── README.md                # documentation (GitHub-ready)
├── src/
│   └── hacker_news_mcp/
│       ├── __init__.py      # package marker
│       ├── server.py        # FastMCP app + entry point
│       ├── lifespan.py      # httpx.AsyncClient lifecycle
│       ├── tools.py         # @mcp.tool — 4 tools
│       ├── resources.py     # @mcp.resource — 2 resources
│       └── prompts.py       # @mcp.prompt — hn_digest
└── .gitignore
```

Create every directory:

```powershell
mkdir -p src/hacker_news_mcp
```

---

## 5. pyproject.toml

```toml
[project]
name = "hacker-news-mcp"
version = "0.1.0"
description = "A FastMCP server for interacting with Hacker News via the Algolia API"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
authors = [{ name = "Your Name" }]
dependencies = [
    "fastmcp>=3.0.0",
    "httpx>=0.27.0",
]

[project.scripts]
hacker-news-mcp = "hacker_news_mcp.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.backends"

[tool.hatch.build.targets.wheel]
packages = ["src/hacker_news_mcp"]
```

> [!NOTE]
> The `[project.scripts]` entry lets you run `hacker-news-mcp` directly after `uv pip install -e .`

---

## 6. Lifespan & Shared Client

**File: `src/hacker_news_mcp/lifespan.py`**

This is the core FastMCP feature that creates a **single shared `httpx.AsyncClient`**
across all tool/resource calls, avoiding per-request client creation overhead.

```python
"""
Lifespan management — shared httpx.AsyncClient across all requests.

FastMCP 3.0 features:
  - @lifespan decorator (from fastmcp.server.lifespan)
  - Yields context dict → accessible via ctx.lifespan_context
  - Composable with | operator if you need multiple lifespans
"""

import httpx
from fastmcp.server.lifespan import lifespan

HN_ALGOLIA_BASE = "https://hn.algolia.com/api/v1"
HN_FIREBASE_BASE = "https://hacker-news.firebaseio.com/v0"


@lifespan
async def hn_lifespan(server):
    """
    Creates a shared httpx.AsyncClient on startup.
    Closes it cleanly on shutdown.
    """
    async with httpx.AsyncClient(
        base_url=HN_ALGOLIA_BASE,
        timeout=httpx.Timeout(30.0),
        headers={"User-Agent": "hacker-news-mcp/0.1.0"},
    ) as algolia_client:
        async with httpx.AsyncClient(
            base_url=HN_FIREBASE_BASE,
            timeout=httpx.Timeout(30.0),
            headers={"User-Agent": "hacker-news-mcp/0.1.0"},
        ) as firebase_client:
            yield {
                "algolia_client": algolia_client,
                "firebase_client": firebase_client,
            }
```

### How It Works

```
Server Start
    │
    ▼
@lifespan creates httpx.AsyncClient instances
    │
    ▼
yield {"algolia_client": ..., "firebase_client": ...}
    │
    ▼ (server runs, tools/resources use ctx.lifespan_context)
    │
Server Stop
    │
    ▼
AsyncClient.__aexit__() → connections closed cleanly
```

---

## 7. Tools Module

**File: `src/hacker_news_mcp/tools.py`**

All 4 tools use **FastMCP 3.0** patterns:
- `CurrentContext()` for context injection (not the old `Context` sentinel)
- `await ctx.info()` and `await ctx.report_progress()` for observability
- Async functions with the shared `httpx.AsyncClient` from lifespan

```python
"""
Tools — callable functions exposed to the MCP client (Claude).

FastMCP 3.0 features demonstrated:
  - @mcp.tool with async functions
  - CurrentContext() dependency injection (3.0 pattern)
  - httpx async external API calls
  - ctx.report_progress for batch fetching
  - ctx.info / ctx.debug for logging API calls
  - Accessing shared httpx client via ctx.lifespan_context
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
from fastmcp import FastMCP
from fastmcp.server.context import Context
from fastmcp.dependencies import CurrentContext


def register_tools(mcp: FastMCP) -> None:
    """Register all HN tools on the given FastMCP server."""

    # ------------------------------------------------------------------ #
    # Tool 1: get_top_stories
    # ------------------------------------------------------------------ #
    @mcp.tool(
        name="get_top_stories",
        description=(
            "Fetch the top N stories from Hacker News with titles, scores, "
            "URLs, authors, and comment counts."
        ),
        tags={"stories", "top"},
    )
    async def get_top_stories(
        limit: int = 10,
        ctx: Context = CurrentContext(),
    ) -> str:
        """Fetch top N stories from HN (default 10, max 30)."""
        limit = min(max(1, limit), 30)

        firebase: httpx.AsyncClient = ctx.lifespan_context["firebase_client"]
        algolia: httpx.AsyncClient = ctx.lifespan_context["algolia_client"]

        await ctx.info(f"Fetching top {limit} story IDs from HN Firebase API")

        # Step 1: Get top story IDs
        resp = await firebase.get("/topstories.json")
        resp.raise_for_status()
        story_ids: list[int] = resp.json()[:limit]

        stories = []
        total = len(story_ids)

        # Step 2: Fetch each story with progress reporting
        for i, story_id in enumerate(story_ids):
            await ctx.report_progress(progress=i, total=total)
            await ctx.debug(f"Fetching story {story_id} ({i+1}/{total})")

            item_resp = await firebase.get(f"/item/{story_id}.json")
            item_resp.raise_for_status()
            item = item_resp.json()

            if item:
                stories.append({
                    "id": item.get("id"),
                    "title": item.get("title", "Untitled"),
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

    # ------------------------------------------------------------------ #
    # Tool 2: get_story_details
    # ------------------------------------------------------------------ #
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
        """Fetch a single story with its comments."""
        firebase: httpx.AsyncClient = ctx.lifespan_context["firebase_client"]

        await ctx.info(f"Fetching story details for ID {story_id}")

        # Fetch the story
        resp = await firebase.get(f"/item/{story_id}.json")
        resp.raise_for_status()
        story = resp.json()

        if not story:
            return json.dumps({"error": f"Story {story_id} not found"})

        # Fetch top-level comments (up to 10)
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

    # ------------------------------------------------------------------ #
    # Tool 3: search_stories
    # ------------------------------------------------------------------ #
    @mcp.tool(
        name="search_stories",
        description=(
            "Search Hacker News via the Algolia API. Supports full-text "
            "query and optional date range filtering."
        ),
        tags={"search", "algolia"},
    )
    async def search_stories(
        query: str,
        days_back: int = 7,
        limit: int = 10,
        ctx: Context = CurrentContext(),
    ) -> str:
        """
        Search HN stories by keyword.

        Args:
            query: Search terms (full-text).
            days_back: How far back to search (default 7 days).
            limit: Max results to return (default 10, max 30).
        """
        limit = min(max(1, limit), 30)
        algolia: httpx.AsyncClient = ctx.lifespan_context["algolia_client"]

        # Calculate timestamp for date range
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
        for hit in data.get("hits", []):
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

    # ------------------------------------------------------------------ #
    # Tool 4: get_user
    # ------------------------------------------------------------------ #
    @mcp.tool(
        name="get_user",
        description="Fetch a Hacker News user profile by username.",
        tags={"user", "profile"},
    )
    async def get_user(
        username: str,
        ctx: Context = CurrentContext(),
    ) -> str:
        """Fetch HN user profile."""
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
```

### Tools API Quick-Reference

| Tool               | Parameters                       | API Endpoint                      |
| ------------------- | -------------------------------- | --------------------------------- |
| `get_top_stories`   | `limit: int = 10`               | Firebase `/topstories.json`       |
| `get_story_details` | `story_id: int`                 | Firebase `/item/{id}.json`        |
| `search_stories`    | `query, days_back=7, limit=10`  | Algolia `/search`                 |
| `get_user`          | `username: str`                 | Firebase `/user/{username}.json`  |

---

## 8. Resources Module

**File: `src/hacker_news_mcp/resources.py`**

```python
"""
Resources — data exposed at stable URIs for the MCP client to read.

FastMCP 3.0 features demonstrated:
  - @mcp.resource with static URI (hn://stories/top)
  - @mcp.resource with URI template (hn://item/{item_id})
  - CurrentContext() dependency injection (3.0 pattern)
  - Async resources with lifespan context access
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
from fastmcp import FastMCP
from fastmcp.server.context import Context
from fastmcp.dependencies import CurrentContext


def register_resources(mcp: FastMCP) -> None:
    """Register all HN resources on the given FastMCP server."""

    # ------------------------------------------------------------------ #
    # Resource 1: hn://stories/top — static snapshot of top stories
    # ------------------------------------------------------------------ #
    @mcp.resource(
        uri="hn://stories/top",
        name="TopStories",
        description="Static snapshot of the current top 20 Hacker News stories.",
        mime_type="application/json",
        tags={"stories", "top"},
    )
    async def top_stories_resource(ctx: Context = CurrentContext()) -> str:
        """Returns a JSON snapshot of the current top 20 HN stories."""
        firebase = ctx.lifespan_context["firebase_client"]

        await ctx.info("Resource read: hn://stories/top")

        resp = await firebase.get("/topstories.json")
        resp.raise_for_status()
        story_ids = resp.json()[:20]

        stories = []
        for i, sid in enumerate(story_ids):
            await ctx.report_progress(progress=i, total=20)
            item_resp = await firebase.get(f"/item/{sid}.json")
            item_resp.raise_for_status()
            item = item_resp.json()
            if item:
                stories.append({
                    "id": item.get("id"),
                    "title": item.get("title", "Untitled"),
                    "url": item.get("url", ""),
                    "score": item.get("score", 0),
                    "by": item.get("by", "unknown"),
                    "descendants": item.get("descendants", 0),
                    "time": datetime.fromtimestamp(
                        item.get("time", 0), tz=timezone.utc
                    ).isoformat(),
                })

        await ctx.report_progress(progress=20, total=20)
        return json.dumps(stories, indent=2)

    # ------------------------------------------------------------------ #
    # Resource 2: hn://item/{item_id} — individual item by ID (template)
    # ------------------------------------------------------------------ #
    @mcp.resource(
        uri="hn://item/{item_id}",
        name="HNItem",
        description="Fetch any Hacker News item (story, comment, poll, job) by its ID.",
        mime_type="application/json",
        tags={"item", "detail"},
    )
    async def item_resource(item_id: int, ctx: Context = CurrentContext()) -> str:
        """Returns a single HN item as JSON, resolved by URI template."""
        firebase = ctx.lifespan_context["firebase_client"]

        await ctx.info(f"Resource read: hn://item/{item_id}")

        resp = await firebase.get(f"/item/{item_id}.json")
        resp.raise_for_status()
        item = resp.json()

        if not item:
            return json.dumps({"error": f"Item {item_id} not found"})

        result = {
            "id": item.get("id"),
            "type": item.get("type", "unknown"),
            "title": item.get("title", ""),
            "text": item.get("text", ""),
            "url": item.get("url", ""),
            "score": item.get("score", 0),
            "by": item.get("by", "[deleted]"),
            "time": datetime.fromtimestamp(
                item.get("time", 0), tz=timezone.utc
            ).isoformat(),
            "descendants": item.get("descendants", 0),
            "kids_count": len(item.get("kids", [])),
        }

        return json.dumps(result, indent=2)
```

### Resource URI Patterns

| URI                 | Type       | Description                                 |
| ------------------- | ---------- | ------------------------------------------- |
| `hn://stories/top`  | Static     | Snapshot of current top 20 stories          |
| `hn://item/{item_id}` | Template | Any HN item by numeric ID                  |

> [!TIP]
> URI templates use `{parameter}` placeholders that FastMCP automatically maps to function arguments.
> When a client requests `hn://item/12345`, FastMCP calls `item_resource(item_id=12345)`.

---

## 9. Prompts Module

**File: `src/hacker_news_mcp/prompts.py`**

```python
"""
Prompts — reusable prompt templates for Claude.

FastMCP 3.0 features demonstrated:
  - @mcp.prompt decorator
  - Multi-message prompt with Message objects (3.0 requirement — raw dicts removed)
  - Parameterized prompts with defaults
  - Message(content, role=...) — role defaults to "user"
"""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.prompts import Message


def register_prompts(mcp: FastMCP) -> None:
    """Register all HN prompts on the given FastMCP server."""

    @mcp.prompt(
        name="hn_digest",
        description=(
            "Generates a daily Hacker News briefing prompt. "
            "Claude will use the available tools to fetch stories, "
            "summarize them, and present a curated digest."
        ),
        tags={"digest", "briefing"},
    )
    def hn_digest(
        num_stories: int = 10,
        include_comments: bool = True,
    ) -> list[Message]:
        """
        Prompt template for a daily HN digest briefing.

        Args:
            num_stories: Number of top stories to include (default 10).
            include_comments: Whether to include top comments (default True).
        """
        comment_instruction = ""
        if include_comments:
            comment_instruction = (
                "\n- For the top 3 most-discussed stories, also fetch their "
                "comments using `get_story_details` and include a brief "
                "summary of the community discussion."
            )

        return [
            Message(
                role="user",
                content=f"""Please create a **Daily Hacker News Digest** briefing. Follow these steps:

1. **Fetch Stories**: Use the `get_top_stories` tool with limit={num_stories} to get today's top stories.

2. **Organize by Category**: Group the stories into these categories:
   - 🚀 **Tech & Engineering** — programming, infrastructure, tools
   - 🤖 **AI & ML** — artificial intelligence, machine learning, LLMs
   - 💼 **Business & Startups** — funding, launches, acquisitions
   - 🔬 **Science & Research** — papers, discoveries, space
   - 📱 **Product & Design** — UX, apps, consumer tech
   - 💬 **Community & Culture** — HN meta, tech culture, essays

3. **Format Each Story**:
   - **Title** (linked to URL)
   - ⬆ Score | 💬 Comment count | 👤 Author
   - One-sentence summary of why it matters
{comment_instruction}

4. **Add a TL;DR Section** at the top with 3 bullet points capturing the day's biggest themes.

5. **Closing**: End with a "🔍 Worth Watching" section highlighting 1-2 stories that could have significant future implications.

**Formatting**: Use clean markdown with emojis for visual scanning. Keep summaries crisp and insightful. The tone should be like a knowledgeable tech friend giving you the morning briefing over coffee.""",
            ),
            Message(
                role="assistant",
                content=(
                    "I'll create your Daily Hacker News Digest now. "
                    "Let me start by fetching the top stories..."
                ),
            ),
        ]
```

---

## 10. Server Entry Point

**File: `src/hacker_news_mcp/__init__.py`**

```python
"""hacker-news-mcp — FastMCP server for Hacker News."""
```

**File: `src/hacker_news_mcp/server.py`**

```python
"""
Main server entry point — wires everything together.

FastMCP 3.0 features demonstrated:
  - FastMCP() constructor with lifespan (no host/port — moved to run())
  - Modular tool/resource/prompt registration
  - Dual transport: stdio (default) + streamable-http
  - mcp.run(transport=..., host=..., port=...) — 3.0 pattern
"""

from __future__ import annotations

import sys

from fastmcp import FastMCP

from hacker_news_mcp.lifespan import hn_lifespan
from hacker_news_mcp.tools import register_tools
from hacker_news_mcp.resources import register_resources
from hacker_news_mcp.prompts import register_prompts


# ── Create the FastMCP server ──────────────────────────────────────────────
# NOTE (FastMCP 3.0): host/port are NO LONGER passed to the constructor.
# They go to mcp.run() instead.
mcp = FastMCP(
    name="hacker-news-mcp",
    instructions=(
        "A Hacker News MCP server. Use the provided tools to fetch stories, "
        "search HN, and get user profiles. Use the hn_digest prompt for a "
        "curated daily briefing."
    ),
    lifespan=hn_lifespan,
)

# ── Register components ───────────────────────────────────────────────────
register_tools(mcp)
register_resources(mcp)
register_prompts(mcp)


# ── Entry point ───────────────────────────────────────────────────────────
def main():
    """
    CLI entry point with dual transport support.

    Usage:
      hacker-news-mcp              → runs with stdio (default, for Claude Desktop)
      hacker-news-mcp --http       → runs with streamable-http on port 8000
    """
    if "--http" in sys.argv:
        # Streamable HTTP transport — for web clients, multi-client access
        mcp.run(
            transport="streamable-http",
            host="127.0.0.1",
            port=8000,
            path="/mcp",
        )
    else:
        # stdio transport — default, for Claude Desktop integration
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

### Transport Comparison

| Transport          | Use Case                    | Start Command                       |
| ------------------ | --------------------------- | ----------------------------------- |
| `stdio`            | Claude Desktop, local CLI   | `uv run hacker-news-mcp`           |
| `streamable-http`  | Web clients, multi-user     | `uv run hacker-news-mcp --http`    |

> [!IMPORTANT]
> When using `streamable-http`, the server listens at `http://127.0.0.1:8000/mcp`.
> Clients send JSON-RPC over standard HTTP POST, with optional SSE for streaming.

---

## 11. Claude Desktop Config

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "hacker-news-mcp": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "C:/path/to/hacker-news-mcp",
        "hacker-news-mcp"
      ]
    }
  }
}
```

> [!TIP]
> Replace the path with your actual project directory. The `--directory` flag tells uv
> where to find the `pyproject.toml`.

---

## 12. Running the Server

### Option A: stdio (for Claude Desktop)

```powershell
# Runs the server with stdio. Claude Desktop connects automatically.
cd hacker-news-mcp
uv run hacker-news-mcp
```

### Option B: Streamable HTTP (for dev/testing)

```powershell
# Starts an HTTP server at http://127.0.0.1:8000/mcp
cd hacker-news-mcp
uv run hacker-news-mcp --http
```

### Option C: FastMCP Dev Inspector

```powershell
# Opens the FastMCP web inspector for interactive testing
cd hacker-news-mcp
fastmcp dev src/hacker_news_mcp/server.py
```

---

## 13. Testing & Verification

### Quick Smoke Test

```powershell
# Test the server starts and tools are registered
uv run fastmcp dev src/hacker_news_mcp/server.py
```

This opens the **MCP Inspector** — a web UI where you can:

1. See all registered **tools**, **resources**, and **prompts**
2. Call `get_top_stories(limit=3)` and verify JSON output
3. Call `search_stories(query="python", days_back=3)`
4. Read `hn://stories/top` resource
5. Read `hn://item/1` resource (the very first HN item)
6. Invoke `hn_digest` prompt

### Programmatic Client Test

```python
"""Quick test script — save as test_client.py and run with uv run test_client.py"""

import asyncio
from fastmcp import Client

async def main():
    client = Client("src/hacker_news_mcp/server.py")

    async with client:
        # List tools
        tools = await client.list_tools()
        print(f"✅ Found {len(tools)} tools:")
        for t in tools:
            print(f"   - {t.name}: {t.description[:60]}...")

        # List resources
        resources = await client.list_resources()
        print(f"\n✅ Found {len(resources)} resources")

        # Call a tool
        result = await client.call_tool("get_top_stories", {"limit": 3})
        print(f"\n✅ get_top_stories returned {len(result)} content blocks")

        # Read a resource
        content = await client.read_resource("hn://item/1")
        print(f"\n✅ hn://item/1 → {content[:100]}...")

asyncio.run(main())
```

---

## 14. README.md

Create this file in the project root:

````markdown
# 🔶 hacker-news-mcp

A [FastMCP 3.0](https://gofastmcp.com) server that gives Claude (and any MCP client)
access to **Hacker News** through the public Algolia API.

## Features

| Category   | Details                                                     |
| ---------- | ----------------------------------------------------------- |
| **Tools**  | `get_top_stories`, `get_story_details`, `search_stories`, `get_user` |
| **Resources** | `hn://stories/top`, `hn://item/{id}`                     |
| **Prompts** | `hn_digest` — daily briefing template                      |
| **Transports** | stdio (Claude Desktop) + streamable-http (web)          |

## Quick Start

```bash
# Clone & install
git clone https://github.com/your-username/hacker-news-mcp.git
cd hacker-news-mcp
uv sync

# Run with stdio
uv run hacker-news-mcp

# Run with HTTP
uv run hacker-news-mcp --http
```

## Claude Desktop Setup

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hacker-news-mcp": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/hacker-news-mcp",
        "hacker-news-mcp"
      ]
    }
  }
}
```

## Architecture

```
                     ┌─────────────────────┐
                     │    Claude Desktop    │
                     │    or MCP Client     │
                     └─────────┬───────────┘
                               │ stdio / streamable-http
                     ┌─────────▼───────────┐
                     │   FastMCP Server     │
                     │  hacker-news-mcp     │
                     ├─────────────────────┤
                     │  Tools  │ Resources  │
                     │  Prompts│ Lifespan   │
                     └─────────┬───────────┘
                               │ httpx async
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
      ┌──────────────┐ ┌─────────────┐  ┌────────────┐
      │ HN Firebase  │ │ HN Algolia  │  │  HN Users  │
      │   API        │ │   API       │  │   API      │
      └──────────────┘ └─────────────┘  └────────────┘
```

## Tools Reference

| Tool               | Description                   | Key Args                    |
| ------------------- | ----------------------------- | --------------------------- |
| `get_top_stories`   | Fetch top HN stories          | `limit` (1-30)              |
| `get_story_details` | Story + comments by ID        | `story_id`                  |
| `search_stories`    | Full-text search via Algolia  | `query`, `days_back`, `limit` |
| `get_user`          | User profile & karma          | `username`                  |

## FastMCP 3.0 Features Covered

- ✅ `@mcp.tool` with async httpx calls
- ✅ `@mcp.resource` with URI templates (`hn://item/{id}`)
- ✅ `@mcp.prompt` with `Message` objects (3.0 requirement)
- ✅ `CurrentContext()` dependency injection (3.0 pattern)
- ✅ `ctx.report_progress` for batch operations
- ✅ `ctx.info` / `ctx.debug` for request logging
- ✅ `@lifespan` — shared `httpx.AsyncClient`
- ✅ `mcp.run(transport=..., host=..., port=...)` (3.0 pattern)
- ✅ Dual transport: `stdio` + `streamable-http`

## License

MIT
````

---

## .gitignore

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.eggs/

# Virtual environments
.venv/
venv/

# uv
uv.lock

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

---

## Feature Mapping Cheat Sheet

| FastMCP 3.0 Feature                      | Where It's Used               | Code Location         |
| ---------------------------------------- | ----------------------------- | --------------------- |
| `CurrentContext()` injection             | All tools + resources         | `tools.py`, `resources.py` |
| `@mcp.tool` with async + httpx          | All 4 tools                   | `tools.py`            |
| `@mcp.resource` (static URI)            | `hn://stories/top`            | `resources.py`        |
| `@mcp.resource` (URI template)          | `hn://item/{item_id}`         | `resources.py`        |
| `@mcp.prompt` with `Message`            | `hn_digest`                   | `prompts.py`          |
| `ctx.report_progress`                   | `get_top_stories`, resources  | `tools.py`            |
| `ctx.info` / `ctx.debug`                | Every tool & resource         | `tools.py`            |
| `@lifespan` + shared client             | `httpx.AsyncClient` lifecycle | `lifespan.py`         |
| `mcp.run(transport=..., host=..., port=...)` | stdio + streamable-http   | `server.py`           |

---

## FastMCP 2.x → 3.0 Migration Cheat Sheet

```diff
# Context injection
- from fastmcp import FastMCP, Context
- from fastmcp.server.context import Context as ContextType
- async def my_tool(ctx: ContextType = Context):
+ from fastmcp.server.context import Context
+ from fastmcp.dependencies import CurrentContext
+ async def my_tool(ctx: Context = CurrentContext()):

# Server constructor
- mcp = FastMCP("server", host="0.0.0.0", port=8080)
- mcp.run()
+ mcp = FastMCP("server")
+ mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)

# Prompts — raw dicts no longer accepted
- return [{"role": "user", "content": "Hello"}]
+ from fastmcp.prompts import Message
+ return [Message("Hello")]

# State methods are now async
- ctx.set_state("key", "value")
+ await ctx.set_state("key", "value")

# Duplicate handling consolidated
- FastMCP("s", on_duplicate_tools="error", on_duplicate_resources="warn")
+ FastMCP("s", on_duplicate="error")

# Meta key renamed
- tool.meta.get("_fastmcp", {})
+ tool.meta.get("fastmcp", {})

# httpx type hints — no longer need string forward references
- firebase: "httpx.AsyncClient" = ctx.lifespan_context["firebase_client"]
+ firebase: httpx.AsyncClient = ctx.lifespan_context["firebase_client"]
```

---

> **Next step**: Copy each code block into the corresponding file, run `uv sync`, then `fastmcp dev src/hacker_news_mcp/server.py` to verify everything works in the MCP Inspector.
