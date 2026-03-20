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
git clone https://github.com/cubaseuser123/hacker-news-mcp.git
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

