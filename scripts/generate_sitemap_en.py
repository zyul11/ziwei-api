#!/usr/bin/env python3
"""Generate sitemap_en.xml by scanning articles/en/ directory"""
from pathlib import Path
from datetime import date, datetime

BASE_DIR = Path(__file__).resolve().parent.parent
ARTICLES_DIR = BASE_DIR / "articles" / "en"
SITEMAP_PATH = BASE_DIR / "sitemap_en.xml"
SITE_URL = "https://ziweiapi.site"

today = date.today().isoformat()

urls = [
    f"  <url>\n    <loc>{SITE_URL}/api-docs.html?lang=en</loc>\n    <priority>0.9</priority>\n    <lastmod>{today}</lastmod>\n  </url>",
    f"  <url>\n    <loc>{SITE_URL}/articles/en/</loc>\n    <priority>0.7</priority>\n    <lastmod>{today}</lastmod>\n  </url>",
]

if ARTICLES_DIR.exists():
    files = sorted(ARTICLES_DIR.glob("*.html"), reverse=True)
    for f in files:
        if f.name == "index.html":
            continue
        urls.append(f'  <url>\n    <loc>{SITE_URL}/articles/en/{f.name}</loc>\n    <priority>0.6</priority>\n    <lastmod>{today}</lastmod>\n  </url>')

sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>
"""

SITEMAP_PATH.write_text(sitemap, encoding="utf-8")
print(f"✅ sitemap_en.xml generated with {len(urls)} URLs")
