"""
Daily Brief HTML Renderer
Generates a clean, mobile-friendly HTML briefing page from summarized stories.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)


def render_brief(
    summaries: dict[str, list[dict]],
    config: dict,
    template_dir: Optional[Path] = None,
    generated_at: Optional[datetime] = None,
) -> str:
    """
    Render the daily brief as HTML.
    Returns the HTML string.
    """
    if template_dir is None:
        template_dir = Path(__file__).parent.parent / "templates"

    if generated_at is None:
        generated_at = datetime.now(tz=timezone.utc)

    settings = config.get("settings", {})
    categories_config = config.get("categories", {})

    # Build enriched category data
    cats = []
    for cat_key, stories in summaries.items():
        cat_cfg = categories_config.get(cat_key, {})
        if not stories:
            continue
        cats.append({
            "key": cat_key,
            "label": cat_cfg.get("label", cat_key.replace("_", " ").title()),
            "color": cat_cfg.get("color", "#6366f1"),
            "stories": stories,
        })

    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("brief.html.j2")

    return template.render(
        title=settings.get("brief_title", "Daily Brief"),
        subtitle=settings.get("brief_subtitle", "Your morning digest"),
        categories=cats,
        generated_at=generated_at,
        date_str=generated_at.strftime("%A, %B %-d, %Y"),
        total_stories=sum(len(s) for s in summaries.values()),
    )


def save_brief(html: str, output_path: Path) -> None:
    """Write HTML to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    logger.info(f"Brief saved to {output_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test render with dummy data
    cfg_path = Path(__file__).parent.parent / "config" / "sources.json"
    with open(cfg_path) as f:
        cfg = json.load(f)

    dummy = {
        "tech": [
            {
                "title": "OpenAI releases GPT-5",
                "url": "https://example.com",
                "summary": "New model achieves significant reasoning improvements.",
                "source": "Tech News",
                "published": "2024-01-01",
            }
        ],
        "business": [
            {
                "title": "Fed holds rates steady",
                "url": "https://example.com/fed",
                "summary": "Federal Reserve keeps rates at current levels amid inflation concerns.",
                "source": "Reuters",
                "published": "2024-01-01",
            }
        ],
    }

    html = render_brief(dummy, cfg)
    out = Path(__file__).parent.parent / "output" / "index.html"
    save_brief(html, out)
    print(f"Test render saved to {out}")
