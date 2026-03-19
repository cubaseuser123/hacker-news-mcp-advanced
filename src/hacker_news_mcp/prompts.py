from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.prompts import Message

def register_prompts(mcp: FastMCP) -> None:

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