"""
Daily Brief Scraper
Pulls stories from RSS feeds, Hacker News API, Dev.to API, and NewsAPI.
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import re

import feedparser
import requests

logger = logging.getLogger(__name__)


def clean_html(text: str) -> str:
    """Strip HTML tags from text."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:500]  # cap at 500 chars for summaries


def fetch_rss(source: dict, timeout: int = 10) -> list[dict]:
    """Fetch items from an RSS/Atom feed."""
    url = source["url"]
    max_items = source.get("max_items", 5)
    stories = []

    try:
        feed = feedparser.parse(url, request_headers={
            "User-Agent": "DailyBrief/1.0"
        })
        if feed.bozo and not feed.entries:
            logger.warning(f"RSS parse issue for {source['name']}: {feed.bozo_exception}")
            return stories

        for entry in feed.entries[:max_items]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            summary = clean_html(
                entry.get("summary", "") or entry.get("description", "")
            )
            published = entry.get("published", "") or entry.get("updated", "")

            if title and link:
                stories.append({
                    "title": title,
                    "url": link,
                    "summary": summary,
                    "source": source["name"],
                    "published": published,
                })
    except Exception as e:
        logger.error(f"Error fetching RSS {url}: {e}")

    return stories


def fetch_hackernews(source: dict, timeout: int = 10) -> list[dict]:
    """Fetch top stories from Hacker News API."""
    max_items = source.get("max_items", 10)
    min_score = source.get("min_score", 100)
    search_term = source.get("search_term", "").lower()
    stories = []

    try:
        # Get top story IDs
        resp = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            timeout=timeout,
        )
        resp.raise_for_status()
        story_ids = resp.json()[:50]  # fetch top 50, filter down

        fetched = 0
        for sid in story_ids:
            if fetched >= max_items:
                break
            try:
                story_resp = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{sid}.json",
                    timeout=timeout,
                )
                story_resp.raise_for_status()
                item = story_resp.json()

                if not item or item.get("type") != "story":
                    continue
                if item.get("score", 0) < min_score:
                    continue
                if item.get("dead") or item.get("deleted"):
                    continue

                title = item.get("title", "")
                url = item.get("url", f"https://news.ycombinator.com/item?id={sid}")

                if search_term:
                    if search_term not in title.lower():
                        continue

                stories.append({
                    "title": title,
                    "url": url,
                    "summary": f"Score: {item.get('score', 0)} | Comments: {item.get('descendants', 0)}",
                    "source": source["name"],
                    "published": datetime.fromtimestamp(
                        item.get("time", 0), tz=timezone.utc
                    ).strftime("%a, %d %b %Y %H:%M:%S +0000"),
                })
                fetched += 1
                time.sleep(0.05)  # gentle rate limiting
            except Exception as e:
                logger.debug(f"HN item {sid} error: {e}")
                continue

    except Exception as e:
        logger.error(f"Error fetching Hacker News: {e}")

    return stories


def fetch_devto(source: dict, timeout: int = 10) -> list[dict]:
    """Fetch top articles from Dev.to API."""
    tags = source.get("tags", [])
    max_items = source.get("max_items", 5)
    stories = []
    seen_ids = set()

    try:
        for tag in tags:
            if len(stories) >= max_items:
                break
            resp = requests.get(
                "https://dev.to/api/articles",
                params={"tag": tag, "per_page": 5, "top": 7},
                timeout=timeout,
                headers={"User-Agent": "DailyBrief/1.0"},
            )
            resp.raise_for_status()

            for article in resp.json():
                if len(stories) >= max_items:
                    break
                article_id = article.get("id")
                if article_id in seen_ids:
                    continue
                seen_ids.add(article_id)

                stories.append({
                    "title": article.get("title", ""),
                    "url": article.get("url", ""),
                    "summary": article.get("description", "")[:300],
                    "source": f"Dev.to ({tag})",
                    "published": article.get("published_at", ""),
                })

    except Exception as e:
        logger.error(f"Error fetching Dev.to: {e}")

    return stories


def fetch_newsapi(source: dict, api_key: str, timeout: int = 10) -> list[dict]:
    """Fetch articles from NewsAPI."""
    if not api_key:
        logger.warning("NewsAPI key not set, skipping NewsAPI source")
        return []

    max_items = source.get("max_items", 5)
    stories = []

    params = {
        "apiKey": api_key,
        "pageSize": max_items,
        "language": source.get("language", "en"),
    }

    # Top headlines vs everything
    if "category" in source or "country" in source:
        endpoint = "https://newsapi.org/v2/top-headlines"
        if "category" in source:
            params["category"] = source["category"]
        if "country" in source:
            params["country"] = source["country"]
        if "query" in source:
            params["q"] = source["query"]
    else:
        endpoint = "https://newsapi.org/v2/everything"
        params["q"] = source.get("query", "technology")
        params["sortBy"] = "publishedAt"

    try:
        resp = requests.get(endpoint, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        for article in data.get("articles", []):
            title = article.get("title", "") or ""
            if "[Removed]" in title or not title:
                continue
            stories.append({
                "title": title,
                "url": article.get("url", ""),
                "summary": article.get("description", "") or "",
                "source": article.get("source", {}).get("name", source["name"]),
                "published": article.get("publishedAt", ""),
            })

    except Exception as e:
        logger.error(f"Error fetching NewsAPI ({source.get('name')}): {e}")

    return stories


def scrape_all(config: dict, newsapi_key: str = "") -> dict[str, list[dict]]:
    """
    Main entry point: scrape all sources per category.
    Returns {category_key: [story, ...]}
    """
    timeout = config.get("settings", {}).get("request_timeout_seconds", 10)
    max_per_cat = config.get("settings", {}).get("max_stories_per_category", 5)
    results: dict[str, list[dict]] = {}

    for cat_key, cat_cfg in config.get("categories", {}).items():
        cat_stories: list[dict] = []

        for source in cat_cfg.get("sources", []):
            src_type = source.get("type")
            logger.info(f"Fetching [{cat_key}] {source.get('name')} ({src_type})")

            try:
                if src_type == "rss":
                    new_stories = fetch_rss(source, timeout=timeout)
                elif src_type == "hackernews":
                    new_stories = fetch_hackernews(source, timeout=timeout)
                elif src_type == "devto":
                    new_stories = fetch_devto(source, timeout=timeout)
                elif src_type == "newsapi":
                    new_stories = fetch_newsapi(source, api_key=newsapi_key, timeout=timeout)
                else:
                    logger.warning(f"Unknown source type: {src_type}")
                    new_stories = []
            except Exception as e:
                logger.error(f"Unhandled error for {source.get('name')}: {e}")
                new_stories = []

            cat_stories.extend(new_stories)
            logger.info(f"  → {len(new_stories)} stories fetched")

        # Deduplicate by URL
        seen_urls: set[str] = set()
        deduped: list[dict] = []
        for s in cat_stories:
            url = s.get("url", "")
            if url not in seen_urls:
                seen_urls.add(url)
                deduped.append(s)

        results[cat_key] = deduped[:max_per_cat * 3]  # keep extras for AI to select from

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cfg_path = Path(__file__).parent.parent / "config" / "sources.json"
    with open(cfg_path) as f:
        cfg = json.load(f)

    data = scrape_all(cfg)
    for cat, stories in data.items():
        print(f"\n=== {cat.upper()} ({len(stories)} stories) ===")
        for s in stories[:3]:
            print(f"  • {s['title'][:80]}")
