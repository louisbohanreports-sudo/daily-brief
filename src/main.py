#!/usr/bin/env python3
"""
Daily Brief — Main Entry Point
Usage:
  python src/main.py [--config config/sources.json] [--output output/index.html] [--no-ai]
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scraper import scrape_all
from src.summarizer import summarize_all
from src.renderer import render_brief, save_brief


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with open(config_path) as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate daily news brief")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parent.parent / "config" / "sources.json",
        help="Path to sources config JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent.parent / "output" / "index.html",
        help="Output HTML file path",
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Skip AI summarization (use extractive fallback)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and summarize but don't write output file",
    )
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger("main")

    # ── Load config ──────────────────────────────────────────────
    logger.info(f"Loading config: {args.config}")
    config = load_config(args.config)

    # ── API Keys ─────────────────────────────────────────────────
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    newsapi_key = os.environ.get("NEWSAPI_KEY", "")

    if args.no_ai:
        anthropic_key = ""  # force fallback

    if not anthropic_key:
        logger.warning("ANTHROPIC_API_KEY not set — using extractive summaries")
    if not newsapi_key:
        logger.warning("NEWSAPI_KEY not set — NewsAPI sources will be skipped")

    # ── Scrape ───────────────────────────────────────────────────
    logger.info("═" * 50)
    logger.info("PHASE 1: Scraping sources")
    logger.info("═" * 50)
    scraped = scrape_all(config, newsapi_key=newsapi_key)

    total_scraped = sum(len(v) for v in scraped.values())
    logger.info(f"Scraped {total_scraped} total stories across {len(scraped)} categories")

    # ── Summarize ────────────────────────────────────────────────
    logger.info("═" * 50)
    logger.info("PHASE 2: AI summarization")
    logger.info("═" * 50)
    summaries = summarize_all(scraped, config, api_key=anthropic_key)

    total_summarized = sum(len(v) for v in summaries.values())
    logger.info(f"Selected {total_summarized} curated stories")

    # ── Render ───────────────────────────────────────────────────
    logger.info("═" * 50)
    logger.info("PHASE 3: Rendering HTML")
    logger.info("═" * 50)
    html = render_brief(summaries, config, generated_at=datetime.now(tz=timezone.utc))

    if args.dry_run:
        logger.info("Dry run — skipping file write")
        print(f"\nGenerated {len(html):,} bytes of HTML (dry run, not saved)")
    else:
        save_brief(html, args.output)
        logger.info(f"✅ Brief saved: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
