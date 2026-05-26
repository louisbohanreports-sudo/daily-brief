# 📰 Daily Brief

An automated daily intelligence digest — scrapes news feeds, summarizes with Claude AI, and publishes a clean mobile-friendly page to GitHub Pages every morning.

## What It Does

1. **Scrapes** RSS feeds, Hacker News, Dev.to, and NewsAPI
2. **Summarizes** top stories per category with Claude (haiku model — fast & cheap)
3. **Renders** a clean dark-mode HTML page
4. **Deploys** automatically to GitHub Pages via GitHub Actions at 7 AM PST

## Quick Start

### 1. Fork/Clone & Push to GitHub

```bash
git clone https://github.com/YOUR_USERNAME/daily-brief
cd daily-brief
```

### 2. Set Up GitHub Secrets

In your repo → **Settings → Secrets and variables → Actions**, add:

| Secret | Required | Description |
|--------|----------|-------------|
| `ANTHROPIC_API_KEY` | Recommended | Claude API key for AI summaries. Get one at [console.anthropic.com](https://console.anthropic.com). Without it, falls back to extractive summaries. |
| `NEWSAPI_KEY` | Optional | NewsAPI key for broader coverage. Get one free at [newsapi.org](https://newsapi.org). |

### 3. Enable GitHub Pages

In **Settings → Pages**:
- Source: **GitHub Actions**

### 4. Run It

The workflow runs automatically at **7:00 AM PST** every day.

To trigger manually: **Actions → Daily Brief → Run workflow**

---

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set API keys
export ANTHROPIC_API_KEY=sk-ant-...
export NEWSAPI_KEY=...          # optional

# Run
python src/main.py

# Skip AI (faster for testing)
python src/main.py --no-ai

# Verbose logging
python src/main.py --verbose

# Dry run (don't write output file)
python src/main.py --dry-run --verbose
```

Output is written to `output/index.html`. Open it in your browser.

---

## Customizing Sources

Edit `config/sources.json` to add, remove, or tune sources.

### Source Types

**`rss`** — Any RSS or Atom feed:
```json
{
  "type": "rss",
  "name": "My Blog",
  "url": "https://example.com/rss.xml",
  "max_items": 5
}
```

**`hackernews`** — Hacker News top stories:
```json
{
  "type": "hackernews",
  "name": "HN Top",
  "max_items": 10,
  "min_score": 100
}
```

**`devto`** — Dev.to articles by tag:
```json
{
  "type": "devto",
  "name": "Dev.to AI",
  "tags": ["ai", "python"],
  "max_items": 5
}
```

**`newsapi`** — NewsAPI headlines or search:
```json
{
  "type": "newsapi",
  "name": "SF News",
  "query": "San Francisco",
  "language": "en",
  "max_items": 5
}
```

### Adding a Category

```json
"crypto": {
  "label": "₿ Crypto",
  "color": "#f59e0b",
  "sources": [
    {
      "type": "rss",
      "name": "CoinDesk",
      "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
      "max_items": 5
    }
  ]
}
```

### Global Settings

```json
"settings": {
  "max_stories_per_category": 5,       // final stories shown per section
  "summary_model": "claude-3-haiku-20240307",
  "summary_max_tokens": 800,
  "request_timeout_seconds": 10,
  "brief_title": "Lou's Daily Brief",
  "brief_subtitle": "Your morning intelligence digest"
}
```

---

## Project Structure

```
daily-brief/
├── .github/
│   └── workflows/
│       └── daily-brief.yml     # GitHub Actions cron
├── config/
│   └── sources.json            # All sources & settings
├── src/
│   ├── main.py                 # Entry point
│   ├── scraper.py              # RSS, HN, Dev.to, NewsAPI fetchers
│   ├── summarizer.py           # Claude AI summarization
│   └── renderer.py             # Jinja2 → HTML
├── templates/
│   └── brief.html.j2           # HTML template (dark mode, mobile-first)
├── output/                     # Generated HTML (gitignored locally)
├── requirements.txt
└── README.md
```

---

## Cost Estimate

Using `claude-3-haiku-20240307` (cheapest Claude model):

- ~5 categories × ~15 stories each = ~75 stories processed per day
- Each summarization call: ~500 input tokens + ~300 output tokens
- ~5 API calls/day × 800 tokens avg = ~4,000 tokens/day
- **Cost: ~$0.002/day (~$0.06/month)** 🎉

---

## Customizing the Look

Edit `templates/brief.html.j2`. It's a Jinja2 template with vanilla CSS — no build step needed. The dark-mode design uses CSS variables at the top for easy theming.

To switch to light mode, change the `:root` color variables in the `<style>` block.

---

## Troubleshooting

**No stories showing up?**
- Run with `--verbose` to see per-source logs
- Check that RSS URLs are valid and accessible
- NewsAPI sources are skipped without `NEWSAPI_KEY`

**AI summaries not working?**
- Verify `ANTHROPIC_API_KEY` is set correctly
- Run `--no-ai` to confirm scraping works independently

**GitHub Pages not deploying?**
- Check **Settings → Pages → Source** is set to "GitHub Actions"
- Verify the workflow has `pages: write` permissions (it does by default in this config)

---

## License

MIT — do whatever you want with it.
