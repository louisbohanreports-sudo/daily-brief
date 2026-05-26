"""
Daily Brief Summarizer
Uses Claude API to summarize and curate scraped stories per category.
Falls back to extractive summary if no API key is available.
"""

import json
import logging
import os
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are an expert news curator creating a morning briefing. 
Your job is to select the most important, interesting, and relevant stories from a list 
and write a concise, insightful one-sentence summary for each.

Guidelines:
- Pick the top stories (aim for quality over quantity)
- Write summaries that add context, not just restate the headline
- Keep each summary to 1-2 sentences max (under 150 chars)
- Skip duplicate or trivial stories
- Prefer stories with real-world impact or novelty
- Use plain language, no jargon
"""

CATEGORY_PROMPTS = {
    "tech": "Focus on significant product launches, developer tools, security issues, and platform changes.",
    "business": "Focus on market movements, company strategy, funding rounds, and economic trends.",
    "local_sf": "Focus on local policy, housing, tech industry impact on the city, and community news.",
    "ai_ml": "Focus on model releases, research breakthroughs, practical applications, and industry shifts.",
    "personal": "Focus on actionable health/fitness insights, product news relevant to the user's interests.",
}


def summarize_with_claude(
    category_key: str,
    stories: list[dict],
    model: str = "claude-3-haiku-20240307",
    max_tokens: int = 800,
    max_stories: int = 5,
    api_key: Optional[str] = None,
) -> list[dict]:
    """
    Use Claude to select and summarize top stories.
    Returns list of {title, url, summary, source} dicts.
    """
    if not stories:
        return []

    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("No ANTHROPIC_API_KEY set — using extractive fallback")
        return extractive_summary(stories, max_stories)

    client = anthropic.Anthropic(api_key=api_key)

    # Build story list for the prompt
    story_list = "\n".join(
        f"{i+1}. [{s['source']}] {s['title']}\n   {s.get('summary', '')[:200]}"
        for i, s in enumerate(stories)
    )

    cat_hint = CATEGORY_PROMPTS.get(category_key, "Focus on the most newsworthy and impactful stories.")

    user_prompt = f"""Here are today's {category_key.replace('_', ' ')} stories. {cat_hint}

Please select the top {max_stories} most important/interesting stories and return them as a JSON array.
Each item: {{"title": "...", "summary": "1-2 sentence insight", "url_index": <1-based index>}}

Stories:
{story_list}

Return ONLY the JSON array, no other text."""

    try:
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw = resp.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        selected = json.loads(raw)
        result = []
        for item in selected:
            idx = item.get("url_index", 1) - 1
            if 0 <= idx < len(stories):
                orig = stories[idx]
                result.append({
                    "title": item.get("title", orig["title"]),
                    "url": orig["url"],
                    "summary": item.get("summary", orig.get("summary", "")),
                    "source": orig.get("source", ""),
                    "published": orig.get("published", ""),
                })
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude response as JSON: {e}")
        return extractive_summary(stories, max_stories)
    except anthropic.APIError as e:
        logger.error(f"Claude API error: {e}")
        return extractive_summary(stories, max_stories)
    except Exception as e:
        logger.error(f"Unexpected error in summarizer: {e}")
        return extractive_summary(stories, max_stories)


def extractive_summary(stories: list[dict], max_stories: int = 5) -> list[dict]:
    """Fallback: return top N stories with their original summaries."""
    return [
        {
            "title": s["title"],
            "url": s["url"],
            "summary": s.get("summary", "")[:200],
            "source": s.get("source", ""),
            "published": s.get("published", ""),
        }
        for s in stories[:max_stories]
    ]


def summarize_all(
    scraped: dict[str, list[dict]],
    config: dict,
    api_key: Optional[str] = None,
) -> dict[str, list[dict]]:
    """
    Summarize all categories.
    Returns {category_key: [summarized_story, ...]}
    """
    settings = config.get("settings", {})
    model = settings.get("summary_model", "claude-3-haiku-20240307")
    max_tokens = settings.get("summary_max_tokens", 800)
    max_per_cat = settings.get("max_stories_per_category", 5)

    summaries: dict[str, list[dict]] = {}

    for cat_key, stories in scraped.items():
        logger.info(f"Summarizing [{cat_key}] — {len(stories)} input stories")
        summarized = summarize_with_claude(
            category_key=cat_key,
            stories=stories,
            model=model,
            max_tokens=max_tokens,
            max_stories=max_per_cat,
            api_key=api_key,
        )
        summaries[cat_key] = summarized
        logger.info(f"  → {len(summarized)} stories selected")

    return summaries


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test with dummy data
    test_stories = [
        {
            "title": "OpenAI releases GPT-5 with dramatic improvements",
            "url": "https://example.com/1",
            "summary": "New model shows 40% improvement in reasoning benchmarks",
            "source": "Tech News",
        },
        {
            "title": "Python 3.14 drops with major performance gains",
            "url": "https://example.com/2",
            "summary": "2x faster startup, improved GIL removal",
            "source": "Python Blog",
        },
    ]

    result = extractive_summary(test_stories, 2)
    for s in result:
        print(f"  • {s['title']}")
