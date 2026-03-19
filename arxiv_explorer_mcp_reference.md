# 📚 arxiv-explorer-mcp — Complete Code Reference (FastMCP 3.0)

> A FastMCP 3.0 Python MCP server that lets Claude explore **arXiv** papers
> via the public arXiv API (Atom/XML). No auth required.
> Built with `fastmcp>=3.0`, `httpx`, `uv`, Python 3.11+.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [FastMCP 3.0 — What Changed](#2-fastmcp-30--what-changed)
3. [Installation & Project Init](#3-installation--project-init)
4. [Folder Structure](#4-folder-structure)
5. [pyproject.toml](#5-pyprojecttoml)
6. [Lifespan & Shared Client](#6-lifespan--shared-client)
7. [XML Parsing Helpers](#7-xml-parsing-helpers)
8. [Tools Module](#8-tools-module)
9. [Resources Module](#9-resources-module)
10. [Prompts Module](#10-prompts-module)
11. [Server Entry Point](#11-server-entry-point)
12. [Claude Desktop Config](#12-claude-desktop-config)
13. [Running the Server](#13-running-the-server)
14. [Testing & Verification](#14-testing--verification)
15. [README.md](#15-readmemd)

---

## 1. Prerequisites

| Tool     | Version | Install                               |
| -------- | ------- | ------------------------------------- |
| Python   | ≥ 3.11  | [python.org](https://python.org)      |
| uv       | latest  | `pip install uv` or `pipx install uv` |
| fastmcp  | ≥ 3.0.0 | auto-installed via `uv`               |
| httpx    | ≥ 0.27  | auto-installed via `uv`               |

**No API keys needed** — the arXiv API is fully public.

---

## 2. FastMCP 3.0 — What Changed

> [!IMPORTANT]
> This reference uses **FastMCP 3.0** patterns throughout. If you're coming from 2.x,
> here are the key differences baked into every file:

| Area | FastMCP 2.x | FastMCP 3.0 (this guide) |
| --- | --- | --- |
| **Context injection** | `ctx: Context = Context` sentinel | `ctx: Context = CurrentContext()` from `fastmcp.dependencies` |
| **Server config** | `FastMCP("name", host=..., port=...)` | `FastMCP("name")` + `mcp.run(transport="streamable-http", host=..., port=...)` |
| **Duplicate handling** | `on_duplicate_tools=...` etc. | Single `on_duplicate=...` parameter |
| **Prompts** | Accepted raw dicts | Must use `Message` from `fastmcp.prompts` |
| **State methods** | `ctx.set_state()` sync | `await ctx.set_state()` async |
| **Meta key** | `_fastmcp` | `fastmcp` |
| **Tools** | Decorators replaced the function | Decorated functions remain callable |
| **Transports** | `WSTransport` | `StreamableHttpTransport` |

---

## 3. Installation & Project Init

```powershell
# 1. Create and enter project directory
mkdir arxiv-explorer-mcp
cd arxiv-explorer-mcp

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
arxiv-explorer-mcp/
├── pyproject.toml              # project metadata + dependencies
├── .python-version             # 3.11
├── README.md                   # documentation (GitHub-ready)
├── src/
│   └── arxiv_explorer_mcp/
│       ├── __init__.py         # package marker
│       ├── server.py           # FastMCP app + entry point
│       ├── lifespan.py         # httpx.AsyncClient lifecycle
│       ├── parser.py           # Atom XML → Python dict helpers
│       ├── tools.py            # @mcp.tool — 4 tools
│       ├── resources.py        # @mcp.resource — 2 resources
│       └── prompts.py          # @mcp.prompt — research_digest
└── .gitignore
```

Create the package directory:

```powershell
mkdir -p src/arxiv_explorer_mcp
```

---

## 5. pyproject.toml

```toml
[project]
name = "arxiv-explorer-mcp"
version = "0.1.0"
description = "A FastMCP 3.0 server for exploring arXiv papers via the public arXiv API"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
authors = [{ name = "Your Name" }]
dependencies = [
    "fastmcp>=3.0.0",
    "httpx>=0.27.0",
]

[project.scripts]
arxiv-explorer-mcp = "arxiv_explorer_mcp.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.backends"

[tool.hatch.build.targets.wheel]
packages = ["src/arxiv_explorer_mcp"]
```

> [!NOTE]
> The `[project.scripts]` entry creates the CLI command `arxiv-explorer-mcp`
> after `uv pip install -e .` or when running with `uv run`.

---

## 6. Lifespan & Shared Client

**File: `src/arxiv_explorer_mcp/lifespan.py`**

Uses FastMCP 3.0's `@lifespan` decorator to create a **single shared `httpx.AsyncClient`**
that persists for the entire server lifetime.

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

ARXIV_API_BASE = "https://export.arxiv.org"


@lifespan
async def arxiv_lifespan(server):
    """
    Creates a shared httpx.AsyncClient on startup.
    The arXiv API recommends a 3-second delay between requests,
    so we set a generous timeout.
    """
    async with httpx.AsyncClient(
        base_url=ARXIV_API_BASE,
        timeout=httpx.Timeout(30.0),
        headers={"User-Agent": "arxiv-explorer-mcp/0.1.0"},
        follow_redirects=True,
    ) as client:
        yield {"arxiv_client": client}
```

### How It Works

```
Server Start
    │
    ▼
@lifespan creates httpx.AsyncClient(base_url="https://export.arxiv.org")
    │
    ▼
yield {"arxiv_client": client}
    │
    ▼ (server runs — tools/resources use ctx.lifespan_context["arxiv_client"])
    │
Server Stop
    │
    ▼
AsyncClient.__aexit__() → connections closed cleanly
```

> [!TIP]
> FastMCP 3.0 lifespans are **composable** — you can combine multiple with `lifespan_a | lifespan_b`.
> They enter left-to-right and exit right-to-left, merging their yielded dicts.

---

## 7. XML Parsing Helpers

**File: `src/arxiv_explorer_mcp/parser.py`**

The arXiv API returns **Atom 1.0 XML**, so we need a small parser to extract structured data.
This keeps the tools and resources clean.

```python
"""
ArXiv Atom XML parser — converts arXiv API responses to Python dicts.

The arXiv API returns Atom 1.0 XML with namespaces:
  - Atom: http://www.w3.org/2005/Atom
  - arXiv: http://arxiv.org/schemas/atom
  - OpenSearch: http://a9.com/-/spec/opensearch/1.1/
"""

from __future__ import annotations

import re
from xml.etree import ElementTree as ET

# XML namespaces used by the arXiv Atom feed
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}


def extract_arxiv_id(id_url: str) -> str:
    """Extract the arXiv paper ID from the full URL.

    'http://arxiv.org/abs/2301.12345v2' → '2301.12345v2'
    """
    match = re.search(r"abs/(.+)$", id_url)
    return match.group(1) if match else id_url


def parse_entry(entry: ET.Element) -> dict:
    """Parse a single Atom <entry> element into a clean dict."""

    # Extract all authors
    authors = []
    for author_elem in entry.findall("atom:author", NS):
        name = author_elem.findtext("atom:name", default="Unknown", namespaces=NS)
        authors.append(name)

    # Extract categories
    categories = []
    for cat_elem in entry.findall("atom:category", NS):
        term = cat_elem.get("term", "")
        if term:
            categories.append(term)

    # Extract arXiv-specific fields
    comment = entry.findtext("arxiv:comment", default="", namespaces=NS)
    journal_ref = entry.findtext("arxiv:journal_ref", default="", namespaces=NS)
    primary_category = ""
    primary_cat_elem = entry.find("arxiv:primary_category", NS)
    if primary_cat_elem is not None:
        primary_category = primary_cat_elem.get("term", "")

    # Extract links
    pdf_url = ""
    abs_url = ""
    for link_elem in entry.findall("atom:link", NS):
        rel = link_elem.get("rel", "")
        href = link_elem.get("href", "")
        link_type = link_elem.get("type", "")
        if rel == "alternate":
            abs_url = href
        elif link_type == "application/pdf":
            pdf_url = href

    raw_id = entry.findtext("atom:id", default="", namespaces=NS)

    return {
        "arxiv_id": extract_arxiv_id(raw_id),
        "title": _clean_text(entry.findtext("atom:title", default="Untitled", namespaces=NS)),
        "summary": _clean_text(entry.findtext("atom:summary", default="", namespaces=NS)),
        "authors": authors,
        "published": entry.findtext("atom:published", default="", namespaces=NS),
        "updated": entry.findtext("atom:updated", default="", namespaces=NS),
        "categories": categories,
        "primary_category": primary_category,
        "pdf_url": pdf_url,
        "abs_url": abs_url or raw_id,
        "comment": comment,
        "journal_ref": journal_ref,
    }


def parse_feed(xml_text: str) -> dict:
    """Parse an entire Atom feed response into a dict with metadata + entries."""
    root = ET.fromstring(xml_text)

    total_results = int(
        root.findtext("opensearch:totalResults", default="0", namespaces=NS)
    )
    start_index = int(
        root.findtext("opensearch:startIndex", default="0", namespaces=NS)
    )
    items_per_page = int(
        root.findtext("opensearch:itemsPerPage", default="0", namespaces=NS)
    )

    entries = [parse_entry(e) for e in root.findall("atom:entry", NS)]

    return {
        "total_results": total_results,
        "start_index": start_index,
        "items_per_page": items_per_page,
        "papers": entries,
    }


def _clean_text(text: str) -> str:
    """Collapse whitespace and strip surrounding spaces."""
    return re.sub(r"\s+", " ", text).strip()
```

---

## 8. Tools Module

**File: `src/arxiv_explorer_mcp/tools.py`**

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
  - ctx.info / ctx.debug for logging
  - Accessing shared httpx client via ctx.lifespan_context
"""

from __future__ import annotations

import json

import httpx
from fastmcp import FastMCP
from fastmcp.server.context import Context
from fastmcp.dependencies import CurrentContext

from arxiv_explorer_mcp.parser import parse_feed, parse_entry


def register_tools(mcp: FastMCP) -> None:
    """Register all arXiv tools on the given FastMCP server."""

    # ------------------------------------------------------------------ #
    # Tool 1: search_papers
    # ------------------------------------------------------------------ #
    @mcp.tool(
        name="search_papers",
        description=(
            "Search arXiv for papers matching a query. Supports keyword search, "
            "author search (au:), title search (ti:), category search (cat:), "
            "and abstract search (abs:). Returns paper metadata with links."
        ),
        tags={"search", "papers"},
    )
    async def search_papers(
        query: str,
        max_results: int = 10,
        sort_by: str = "relevance",
        ctx: Context = CurrentContext(),
    ) -> str:
        """
        Search arXiv papers by keyword, author, or category.

        Args:
            query: Search query. Use field prefixes like 'au:Einstein',
                   'ti:quantum', 'cat:cs.AI', 'abs:transformer'.
                   Combine with AND/OR/ANDNOT.
            max_results: Number of results to return (default 10, max 50).
            sort_by: Sort by 'relevance', 'lastUpdatedDate', or 'submittedDate'.
        """
        max_results = min(max(1, max_results), 50)
        client: httpx.AsyncClient = ctx.lifespan_context["arxiv_client"]

        await ctx.info(f"Searching arXiv for '{query}' (max {max_results}, sort: {sort_by})")

        resp = await client.get(
            "/api/query",
            params={
                "search_query": query,
                "start": 0,
                "max_results": max_results,
                "sortBy": sort_by,
                "sortOrder": "descending",
            },
        )
        resp.raise_for_status()

        result = parse_feed(resp.text)
        await ctx.info(
            f"Found {result['total_results']} total results, "
            f"returning {len(result['papers'])}"
        )

        return json.dumps(result, indent=2)

    # ------------------------------------------------------------------ #
    # Tool 2: get_paper
    # ------------------------------------------------------------------ #
    @mcp.tool(
        name="get_paper",
        description=(
            "Fetch full metadata for a specific arXiv paper by its ID "
            "(e.g., '2301.12345' or '2301.12345v2'). Returns title, "
            "abstract, authors, categories, and PDF/abstract links."
        ),
        tags={"papers", "details"},
    )
    async def get_paper(
        paper_id: str,
        ctx: Context = CurrentContext(),
    ) -> str:
        """Fetch a single arXiv paper by ID."""
        client: httpx.AsyncClient = ctx.lifespan_context["arxiv_client"]

        await ctx.info(f"Fetching paper details for arXiv:{paper_id}")

        resp = await client.get(
            "/api/query",
            params={
                "id_list": paper_id,
                "max_results": 1,
            },
        )
        resp.raise_for_status()

        result = parse_feed(resp.text)

        if not result["papers"]:
            await ctx.warning(f"Paper {paper_id} not found")
            return json.dumps({"error": f"Paper '{paper_id}' not found"})

        paper = result["papers"][0]
        await ctx.info(f"Found paper: '{paper['title']}'")

        return json.dumps(paper, indent=2)

    # ------------------------------------------------------------------ #
    # Tool 3: get_author_papers
    # ------------------------------------------------------------------ #
    @mcp.tool(
        name="get_author_papers",
        description=(
            "Fetch recent papers by a specific author from arXiv. "
            "Returns their latest publications sorted by submission date."
        ),
        tags={"authors", "papers"},
    )
    async def get_author_papers(
        author: str,
        max_results: int = 10,
        ctx: Context = CurrentContext(),
    ) -> str:
        """
        Fetch papers by a specific author.

        Args:
            author: Author name (e.g., 'Yann LeCun', 'Hinton').
            max_results: Number of papers to return (default 10, max 30).
        """
        max_results = min(max(1, max_results), 30)
        client: httpx.AsyncClient = ctx.lifespan_context["arxiv_client"]

        await ctx.info(f"Searching papers by author '{author}' (max {max_results})")

        resp = await client.get(
            "/api/query",
            params={
                "search_query": f"au:{author}",
                "start": 0,
                "max_results": max_results,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            },
        )
        resp.raise_for_status()

        result = parse_feed(resp.text)
        await ctx.info(
            f"Found {result['total_results']} papers by '{author}', "
            f"returning {len(result['papers'])}"
        )

        return json.dumps(result, indent=2)

    # ------------------------------------------------------------------ #
    # Tool 4: get_category_papers
    # ------------------------------------------------------------------ #
    @mcp.tool(
        name="get_category_papers",
        description=(
            "Fetch the most recent papers in a specific arXiv category "
            "(e.g., cs.AI, cs.LG, math.CO, physics.hep-th, stat.ML). "
            "Great for staying current in a research field."
        ),
        tags={"categories", "papers"},
    )
    async def get_category_papers(
        category: str,
        max_results: int = 10,
        ctx: Context = CurrentContext(),
    ) -> str:
        """
        Fetch recent papers from a specific arXiv category.

        Args:
            category: arXiv category code (e.g., 'cs.AI', 'cs.LG',
                      'math.CO', 'physics.hep-th', 'stat.ML').
            max_results: Number of papers to return (default 10, max 30).
        """
        max_results = min(max(1, max_results), 30)
        client: httpx.AsyncClient = ctx.lifespan_context["arxiv_client"]

        await ctx.info(f"Fetching latest {max_results} papers in category '{category}'")

        resp = await client.get(
            "/api/query",
            params={
                "search_query": f"cat:{category}",
                "start": 0,
                "max_results": max_results,
                "sortBy": "lastUpdatedDate",
                "sortOrder": "descending",
            },
        )
        resp.raise_for_status()

        result = parse_feed(resp.text)

        # Report progress while parsing
        total = len(result["papers"])
        for i in range(total):
            await ctx.report_progress(progress=i + 1, total=total)

        await ctx.info(
            f"Retrieved {total} papers from '{category}' "
            f"(out of {result['total_results']} total)"
        )

        return json.dumps(result, indent=2)
```

### Tools API Quick-Reference

| Tool                 | Parameters                              | arXiv Query          |
| -------------------- | --------------------------------------- | -------------------- |
| `search_papers`      | `query, max_results=10, sort_by`        | `search_query=...`   |
| `get_paper`          | `paper_id: str`                         | `id_list=...`        |
| `get_author_papers`  | `author: str, max_results=10`           | `au:{author}`        |
| `get_category_papers`| `category: str, max_results=10`         | `cat:{category}`     |

### arXiv Search Query Syntax

| Prefix  | Meaning         | Example                    |
| ------- | --------------- | -------------------------- |
| `au:`   | Author          | `au:Hinton`                |
| `ti:`   | Title           | `ti:attention mechanism`   |
| `abs:`  | Abstract        | `abs:transformer`          |
| `cat:`  | Category        | `cat:cs.AI`                |
| `all:`  | All fields      | `all:reinforcement learning` |
| `AND`   | Boolean AND     | `au:LeCun AND cat:cs.LG`  |
| `OR`    | Boolean OR      | `cat:cs.AI OR cat:cs.LG`  |
| `ANDNOT`| Boolean NOT     | `cat:cs.AI ANDNOT au:Doe` |

---

## 9. Resources Module

**File: `src/arxiv_explorer_mcp/resources.py`**

```python
"""
Resources — data exposed at stable URIs for the MCP client to read.

FastMCP 3.0 features demonstrated:
  - @mcp.resource with static URI (arxiv://papers/recent)
  - @mcp.resource with URI template (arxiv://paper/{paper_id})
  - CurrentContext() dependency injection (3.0 pattern)
  - Async resources with lifespan context access
"""

from __future__ import annotations

import json

import httpx
from fastmcp import FastMCP
from fastmcp.server.context import Context
from fastmcp.dependencies import CurrentContext

from arxiv_explorer_mcp.parser import parse_feed


def register_resources(mcp: FastMCP) -> None:
    """Register all arXiv resources on the given FastMCP server."""

    # ------------------------------------------------------------------ #
    # Resource 1: arxiv://papers/recent — recent notable papers
    # ------------------------------------------------------------------ #
    @mcp.resource(
        uri="arxiv://papers/recent",
        name="RecentPapers",
        description=(
            "Snapshot of the 20 most recently updated papers across "
            "popular CS/AI categories (cs.AI, cs.LG, cs.CL)."
        ),
        mime_type="application/json",
        tags={"papers", "recent"},
    )
    async def recent_papers_resource(ctx: Context = CurrentContext()) -> str:
        """Returns a JSON snapshot of recent notable arXiv papers."""
        client: httpx.AsyncClient = ctx.lifespan_context["arxiv_client"]

        await ctx.info("Resource read: arxiv://papers/recent")

        # Fetch recent papers from popular AI categories
        resp = await client.get(
            "/api/query",
            params={
                "search_query": "cat:cs.AI OR cat:cs.LG OR cat:cs.CL",
                "start": 0,
                "max_results": 20,
                "sortBy": "lastUpdatedDate",
                "sortOrder": "descending",
            },
        )
        resp.raise_for_status()

        result = parse_feed(resp.text)

        total = len(result["papers"])
        for i in range(total):
            await ctx.report_progress(progress=i + 1, total=total)

        await ctx.info(f"Loaded {total} recent papers")
        return json.dumps(result, indent=2)

    # ------------------------------------------------------------------ #
    # Resource 2: arxiv://paper/{paper_id} — individual paper (template)
    # ------------------------------------------------------------------ #
    @mcp.resource(
        uri="arxiv://paper/{paper_id}",
        name="ArxivPaper",
        description=(
            "Fetch any arXiv paper by its ID (e.g., '2301.12345' or "
            "'2301.12345v2'). Returns full metadata including title, "
            "abstract, authors, categories, and links."
        ),
        mime_type="application/json",
        tags={"paper", "detail"},
    )
    async def paper_resource(
        paper_id: str,
        ctx: Context = CurrentContext(),
    ) -> str:
        """Returns a single arXiv paper as JSON, resolved by URI template."""
        client: httpx.AsyncClient = ctx.lifespan_context["arxiv_client"]

        await ctx.info(f"Resource read: arxiv://paper/{paper_id}")

        resp = await client.get(
            "/api/query",
            params={
                "id_list": paper_id,
                "max_results": 1,
            },
        )
        resp.raise_for_status()

        result = parse_feed(resp.text)

        if not result["papers"]:
            return json.dumps({"error": f"Paper '{paper_id}' not found"})

        paper = result["papers"][0]
        await ctx.info(f"Loaded paper: '{paper['title']}'")

        return json.dumps(paper, indent=2)
```

### Resource URI Patterns

| URI                      | Type       | Description                              |
| ------------------------ | ---------- | ---------------------------------------- |
| `arxiv://papers/recent`  | Static     | Latest 20 papers from cs.AI/LG/CL       |
| `arxiv://paper/{paper_id}` | Template | Any arXiv paper by ID                    |

> [!TIP]
> URI templates use `{parameter}` placeholders that FastMCP automatically maps to function arguments.
> When a client requests `arxiv://paper/2301.12345`, FastMCP calls `paper_resource(paper_id="2301.12345")`.

---

## 10. Prompts Module

**File: `src/arxiv_explorer_mcp/prompts.py`**

```python
"""
Prompts — reusable prompt templates for Claude.

FastMCP 3.0 features demonstrated:
  - @mcp.prompt decorator
  - Multi-message prompt with Message objects (3.0 requirement)
  - Parameterized prompts with defaults
  - Message(content, role=...) — role defaults to "user"
"""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.prompts import Message


def register_prompts(mcp: FastMCP) -> None:
    """Register all arXiv prompts on the given FastMCP server."""

    @mcp.prompt(
        name="research_digest",
        description=(
            "Generates a research digest prompt. Claude will use the "
            "available tools to fetch papers, summarize key findings, "
            "and present a curated research briefing."
        ),
        tags={"digest", "research"},
    )
    def research_digest(
        category: str = "cs.AI",
        num_papers: int = 10,
        include_abstracts: bool = True,
    ) -> list[Message]:
        """
        Prompt template for a research field digest.

        Args:
            category: arXiv category to focus on (default cs.AI).
            num_papers: Number of papers to include (default 10).
            include_abstracts: Include paper abstracts (default True).
        """
        abstract_instruction = ""
        if include_abstracts:
            abstract_instruction = (
                "\n- For the top 3 most interesting papers, include a "
                "2-3 sentence simplified abstract that explains the key "
                "contribution in accessible language."
            )

        return [
            Message(
                role="user",
                content=f"""Please create a **Research Digest** for the arXiv category **{category}**. Follow these steps:

1. **Fetch Papers**: Use the `get_category_papers` tool with category="{category}" and max_results={num_papers}.

2. **Organize by Theme**: Group the papers into logical research themes. Common themes include:
   - 🧠 **Architecture & Models** — new model designs, scaling approaches
   - 📊 **Training & Optimization** — training techniques, efficiency gains
   - 🔬 **Theory & Analysis** — theoretical foundations, proofs, analysis
   - 🛠️ **Applications** — real-world applications, benchmarks, deployments
   - 📐 **Data & Evaluation** — datasets, benchmarks, evaluation methods

3. **Format Each Paper**:
   - **Title** (linked to arXiv abstract page)
   - 👤 Authors (first 3 + "et al." if more)
   - 📂 Primary Category | 📅 Published Date
   - One-sentence "so what" — why this paper matters
{abstract_instruction}

4. **TL;DR Section** at the top: 3 bullet points capturing this batch's biggest trends or breakthroughs.

5. **Connections**: Note any papers that build on each other or address the same problem from different angles.

6. **Closing**: End with a "🔭 Research Frontier" section highlighting 1-2 papers that could represent significant paradigm shifts.

**Formatting**: Use clean markdown with emojis for visual scanning. Explain technical concepts simply — like a well-read colleague summarizing papers over coffee. Prioritize insight over completeness.""",
            ),
            Message(
                role="assistant",
                content=(
                    f"I'll create your Research Digest for **{category}** now. "
                    "Let me start by fetching the latest papers..."
                ),
            ),
        ]
```

---

## 11. Server Entry Point

**File: `src/arxiv_explorer_mcp/__init__.py`**

```python
"""arxiv-explorer-mcp — FastMCP 3.0 server for exploring arXiv papers."""
```

**File: `src/arxiv_explorer_mcp/server.py`**

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

from arxiv_explorer_mcp.lifespan import arxiv_lifespan
from arxiv_explorer_mcp.tools import register_tools
from arxiv_explorer_mcp.resources import register_resources
from arxiv_explorer_mcp.prompts import register_prompts


# ── Create the FastMCP server ──────────────────────────────────────────────
# NOTE (FastMCP 3.0): host/port are NO LONGER passed to the constructor.
# They go to mcp.run() instead.
mcp = FastMCP(
    name="arxiv-explorer-mcp",
    instructions=(
        "An arXiv research paper explorer. Use the provided tools to search "
        "for papers, look up specific papers by ID, explore author publications, "
        "and browse categories. Use the research_digest prompt for a curated "
        "field overview."
    ),
    lifespan=arxiv_lifespan,
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
      arxiv-explorer-mcp              → runs with stdio (default, for Claude Desktop)
      arxiv-explorer-mcp --http       → runs with streamable-http on port 8000
    """
    if "--http" in sys.argv:
        # FastMCP 3.0: host/port/path passed to run(), NOT constructor
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

| Transport          | Use Case                    | Start Command                           |
| ------------------ | --------------------------- | --------------------------------------- |
| `stdio`            | Claude Desktop, local CLI   | `uv run arxiv-explorer-mcp`            |
| `streamable-http`  | Web clients, multi-user     | `uv run arxiv-explorer-mcp --http`     |

> [!IMPORTANT]
> **FastMCP 3.0 change**: `host`, `port`, `path` are passed to `mcp.run()`, NOT to the `FastMCP()` constructor.
> The constructor in 3.0 raises `TypeError` if you pass these arguments directly.

---

## 12. Claude Desktop Config

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "arxiv-explorer-mcp": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "C:/path/to/arxiv-explorer-mcp",
        "arxiv-explorer-mcp"
      ]
    }
  }
}
```

> [!TIP]
> Replace the path with your actual project directory. The `--directory` flag tells uv
> where to find the `pyproject.toml`.

---

## 13. Running the Server

### Option A: stdio (for Claude Desktop)

```powershell
# Runs the server with stdio. Claude Desktop connects automatically.
cd arxiv-explorer-mcp
uv run arxiv-explorer-mcp
```

### Option B: Streamable HTTP (for dev/testing)

```powershell
# Starts an HTTP server at http://127.0.0.1:8000/mcp
cd arxiv-explorer-mcp
uv run arxiv-explorer-mcp --http
```

### Option C: FastMCP Dev Inspector

```powershell
# Opens the FastMCP web inspector for interactive testing
cd arxiv-explorer-mcp
fastmcp dev src/arxiv_explorer_mcp/server.py
```

---

## 14. Testing & Verification

### Quick Smoke Test

```powershell
# Test the server starts and all components are registered
uv run fastmcp dev src/arxiv_explorer_mcp/server.py
```

This opens the **MCP Inspector** — a web UI where you can:

1. See all registered **tools**, **resources**, and **prompts**
2. Call `search_papers(query="transformer", max_results=3)` and verify JSON output
3. Call `get_paper(paper_id="2301.08243")` to fetch a specific paper
4. Call `get_author_papers(author="Yann LeCun", max_results=5)`
5. Call `get_category_papers(category="cs.AI", max_results=5)`
6. Read `arxiv://papers/recent` resource
7. Read `arxiv://paper/2301.08243` resource
8. Invoke `research_digest` prompt

### Programmatic Client Test

```python
"""Quick test script — save as test_client.py and run with uv run test_client.py"""

import asyncio
from fastmcp import Client

async def main():
    client = Client("src/arxiv_explorer_mcp/server.py")

    async with client:
        # List tools
        tools = await client.list_tools()
        print(f"✅ Found {len(tools)} tools:")
        for t in tools:
            print(f"   - {t.name}: {t.description[:60]}...")

        # List resources
        resources = await client.list_resources()
        print(f"\n✅ Found {len(resources)} resources")

        # List prompts
        prompts = await client.list_prompts()
        print(f"✅ Found {len(prompts)} prompts")

        # Call a tool — search for transformer papers
        result = await client.call_tool(
            "search_papers",
            {"query": "ti:transformer attention", "max_results": 3},
        )
        print(f"\n✅ search_papers returned {len(result)} content blocks")

        # Read a resource — specific paper
        content = await client.read_resource("arxiv://paper/2301.08243")
        print(f"\n✅ arxiv://paper/2301.08243 → {str(content)[:120]}...")

asyncio.run(main())
```

---

## 15. README.md

Create this file in the project root:

````markdown
# 📚 arxiv-explorer-mcp

A [FastMCP 3.0](https://gofastmcp.com) server that gives Claude (and any MCP client)
access to **arXiv** papers through the public arXiv API.

## Features

| Category       | Details                                                              |
| -------------- | -------------------------------------------------------------------- |
| **Tools**      | `search_papers`, `get_paper`, `get_author_papers`, `get_category_papers` |
| **Resources**  | `arxiv://papers/recent`, `arxiv://paper/{id}`                        |
| **Prompts**    | `research_digest` — curated field overview template                  |
| **Transports** | stdio (Claude Desktop) + streamable-http (web)                       |

## Quick Start

```bash
# Clone & install
git clone https://github.com/your-username/arxiv-explorer-mcp.git
cd arxiv-explorer-mcp
uv sync

# Run with stdio
uv run arxiv-explorer-mcp

# Run with HTTP
uv run arxiv-explorer-mcp --http
```

## Claude Desktop Setup

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "arxiv-explorer-mcp": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/arxiv-explorer-mcp",
        "arxiv-explorer-mcp"
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
                     │   FastMCP 3.0       │
                     │  arxiv-explorer-mcp │
                     ├─────────────────────┤
                     │  Tools  │ Resources  │
                     │  Prompts│ Lifespan   │
                     │         │ Parser     │
                     └─────────┬───────────┘
                               │ httpx async
                     ┌─────────▼───────────┐
                     │  arXiv API          │
                     │  export.arxiv.org   │
                     │  (Atom XML)         │
                     └─────────────────────┘
```

## Tools Reference

| Tool                 | Description                       | Key Args                      |
| -------------------- | --------------------------------- | ----------------------------- |
| `search_papers`      | Full-text search across arXiv     | `query`, `max_results`, `sort_by` |
| `get_paper`          | Fetch paper by arXiv ID           | `paper_id`                    |
| `get_author_papers`  | Author's latest publications      | `author`, `max_results`       |
| `get_category_papers`| Browse a category's latest papers | `category`, `max_results`     |

## Search Syntax

| Prefix | Meaning   | Example                    |
| ------ | --------- | -------------------------- |
| `au:`  | Author    | `au:Hinton`                |
| `ti:`  | Title     | `ti:attention mechanism`   |
| `abs:` | Abstract  | `abs:transformer`          |
| `cat:` | Category  | `cat:cs.AI`                |
| `AND`  | Boolean   | `au:LeCun AND cat:cs.LG`  |

## FastMCP 3.0 Features Covered

- ✅ `@mcp.tool` with async httpx calls
- ✅ `@mcp.resource` with URI templates (`arxiv://paper/{id}`)
- ✅ `@mcp.prompt` with `Message` objects (3.0 requirement)
- ✅ `CurrentContext()` dependency injection (3.0 pattern)
- ✅ `ctx.report_progress` for batch operations
- ✅ `ctx.info` / `ctx.debug` / `ctx.warning` for logging
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

| FastMCP 3.0 Feature                      | Where It's Used                 | Code Location      |
| ---------------------------------------- | ------------------------------- | -------------------- |
| `CurrentContext()` injection             | All tools + resources           | `tools.py`, `resources.py` |
| `@mcp.tool` with async + httpx          | All 4 tools                     | `tools.py`           |
| `@mcp.resource` (static URI)            | `arxiv://papers/recent`         | `resources.py`       |
| `@mcp.resource` (URI template)          | `arxiv://paper/{paper_id}`      | `resources.py`       |
| `@mcp.prompt` with `Message`            | `research_digest`               | `prompts.py`         |
| `ctx.report_progress`                   | `get_category_papers`, resources | `tools.py`          |
| `ctx.info` / `ctx.debug` / `ctx.warning`| Every tool & resource           | `tools.py`           |
| `@lifespan` + shared client             | `httpx.AsyncClient` lifecycle   | `lifespan.py`        |
| `mcp.run(transport=..., host=..., port=...)` | stdio + streamable-http     | `server.py`          |

---

## FastMCP 2.x → 3.0 Migration Cheat Sheet

```diff
# Context injection
- from fastmcp import Context
- async def my_tool(ctx: Context = Context):
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
```

---

> **Next step**: Copy each code block into the corresponding file, run `uv sync`, then `fastmcp dev src/arxiv_explorer_mcp/server.py` to verify everything works in the MCP Inspector.
